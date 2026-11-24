/*
 * PredictIndex: the script inside the Google Form "Add your study to PredictIndex".
 *
 * What it does
 *   - On every answer it e-mails the people who look after PredictIndex: the study's name,
 *     the address of the person who sent it (only in that e-mail, never on GitHub), and a
 *     link that opens the GitHub form "Add a study" already filled in with the answers.
 *     They check the answers and click Create on GitHub; the rest happens there.
 *   - Every night it reads the label options from PredictIndex's repository on GitHub
 *     (options.json, a public file) and writes them into the form's label questions, so that
 *     the Google Form offers the same options as the page and the GitHub forms.
 *
 * Settings, in the script editor: Project Settings (the cog on the left), Script Properties:
 *   NOTIFY   the e-mail addresses that receive the e-mails, separated by commas
 *   REPO     the GitHub repository; leave it out for predcommlab/network-datasets
 *
 * Setting up, once, by the owner of the form, and again after the form has a new owner (the
 * automatic runs belong to the Google account that started them):
 *   1. In the form: the three dots at the top right, Apps Script. Paste this file over the
 *      code that is there, and save.
 *   2. Fill in the settings above.
 *   3. Choose the function setUp at the top and click Run. The first time, Google asks for
 *      permission; allow it. (For a script of your own, Google first shows a warning: click
 *      Advanced, then Go to ..., then Allow.)
 *   setUp brings the form's questions up to date and starts the two automatic runs (on every
 *   answer; every night). Running it again does no harm.
 *
 * The copy of this file in the repository (google-form/predictindex_form.gs) is the
 * reference; the copy inside the form is the one that runs.
 */

const DEFAULT_REPO = 'predcommlab/network-datasets';
const MULTIPLE = ' (multiple selections possible)';
const LABELS_PAGE = 'Labels';

// The form's questions by title; a former title follows the current one.
const Q = {
  name: ['Study name'],
  authors: ['Authors'],
  corresponding: ['Corresponding author'],
  published: ['Is the study published (or available as a preprint)?', 'Is the study published?'],
  paper: ['Publication / DOI'],
  data: ['Link to the data'],
  participants: ['Number of participants'],
};
// Questions of the first version of the form that nothing uses any more.
const REMOVED = ['PI / group', 'Institution'];
// Label questions that had another title before: the category's key, and its former titles.
const FORMER_TITLES = {taskRelevance: ['Active vs. passive']};


// ------------------------------------------------------------------ setting up

function setUp() {
  const props = PropertiesService.getScriptProperties();
  const notify = (props.getProperty('NOTIFY') || '').trim();
  if (!notify) {
    throw new Error('Please fill in the setting NOTIFY first (Project Settings, Script Properties): ' +
      'the e-mail addresses that receive the e-mails, separated by commas.');
  }
  const form = FormApp.getActiveForm();
  const done = [];

  const published = findItem_(form, Q.published);
  if (published && published.getTitle() !== Q.published[0]) {
    published.setTitle(Q.published[0]);
    done.push('Question renamed: ' + Q.published[0]);
  }
  if (!findItem_(form, Q.corresponding)) {
    form.addTextItem().setTitle(Q.corresponding[0]).setRequired(true)
      .setHelpText('The first and last name of the corresponding author, as on the paper.');
    done.push('Question added: Corresponding author (required)');
  }
  // Right after Authors. Questions are moved by their position: Google's moveItem does not
  // take a text question itself, only a plain question or a position.
  const corresponding = findItem_(form, Q.corresponding), authors = findItem_(form, Q.authors);
  if (authors && corresponding.getIndex() !== authors.getIndex() + 1) {
    const from = corresponding.getIndex(), to = authors.getIndex() + (from > authors.getIndex() ? 1 : 0);
    form.moveItem(from, to);
    done.push('Question moved to right after Authors: Corresponding author');
  }
  REMOVED.forEach(title => {
    const item = findItem_(form, [title]);
    if (item) {
      form.deleteItem(item);
      done.push('Question removed: ' + title);
    }
  });
  done.push(updateOptions());

  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('onAnswer').forForm(form).onFormSubmit().create();
  ScriptApp.newTrigger('updateOptions').timeBased().everyDays(1).atHour(3).create();
  done.push('Automatic runs started: an e-mail to ' + notify + ' on every answer; the options from ' +
    repo_() + ' every night.');
  console.log(done.join('\n'));
}


// ---------------------------------------------------------- the label questions

// Reads options.json from GitHub and makes the label questions match it: one question per
// category, in its order, titled with the category's label, explained with its help text,
// offering its options and "Other". A question is recognised by the ID kept from earlier
// runs, or else by its title, so a renamed category keeps its column in the sheet of
// answers. Label questions of categories that no longer exist are removed. If options.json
// cannot be read, nothing is changed.
function updateOptions() {
  const url = 'https://raw.githubusercontent.com/' + repo_() + '/main/options.json';
  const response = UrlFetchApp.fetch(url, {muteHttpExceptions: true});
  let options = null;
  if (response.getResponseCode() === 200) {
    try { options = JSON.parse(response.getContentText()); } catch (e) { options = null; }
  }
  if (!options || !Array.isArray(options.categories) || !options.categories.length) {
    const said = 'The options could not be read from ' + url + ' (answer ' + response.getResponseCode() +
      '), so the form was not changed.';
    console.log(said);
    return said;
  }

  const form = FormApp.getActiveForm();
  const props = PropertiesService.getScriptProperties();
  const stored = {};
  Object.entries(props.getProperties()).forEach(([k, v]) => { if (k.indexOf('ITEM_') === 0) stored[k.slice(5)] = v; });
  const page = form.getItems(FormApp.ItemType.PAGE_BREAK).filter(p => p.getTitle() === LABELS_PAGE)[0];
  const after = page ? page.getIndex() : -1;
  const current = form.getItems(FormApp.ItemType.CHECKBOX).filter(i => i.getIndex() > after)
    .map(i => ({id: String(i.getId()), title: i.getTitle()}));
  const plan = planLabels_(current, options.categories, stored);

  const counts = {added: 0, changed: 0, removed: 0};
  plan.remove.forEach(id => { form.deleteItem(form.getItemById(Number(id))); counts.removed++; });
  plan.questions.forEach((q, i) => {
    let item = q.id ? form.getItemById(Number(q.id)).asCheckboxItem() : null;
    if (!item) {
      item = form.addCheckboxItem();
      counts.added++;
    } else if (item.getTitle() !== q.title || item.getHelpText() !== q.help ||
               item.getChoices().map(c => c.getValue()).join('\n') !== q.choices.join('\n') || !item.hasOtherOption()) {
      counts.changed++;
    }
    if (item.getTitle() !== q.title) item.setTitle(q.title);
    if (item.getHelpText() !== q.help) item.setHelpText(q.help);
    if (item.getChoices().map(c => c.getValue()).join('\n') !== q.choices.join('\n')) item.setChoiceValues(q.choices);
    if (!item.hasOtherOption()) item.showOtherOption(true);
    if (item.getIndex() !== after + 1 + i) form.moveItem(item.getIndex(), after + 1 + i);
    props.setProperty('ITEM_' + q.key, String(item.getId()));
  });
  Object.keys(stored).forEach(key => {
    if (!plan.questions.some(q => q.key === key)) props.deleteProperty('ITEM_' + key);
  });
  return 'Label questions: ' + plan.questions.length + ' (' + counts.added + ' added, ' + counts.changed +
    ' changed, ' + counts.removed + ' removed), from ' + url;
}

// Which existing question becomes which category's question. current: [{id, title}] of the
// checkbox questions on the labels page; stored: {category key: question ID} from earlier runs.
function planLabels_(current, categories, stored) {
  const bare = t => String(t).replace(MULTIPLE, '').trim().toLowerCase();
  const taken = {};
  const questions = categories.map(c => {
    let found = current.filter(i => i.id === stored[c.key] && !taken[i.id])[0];
    if (!found) {
      const titles = [c.label].concat(FORMER_TITLES[c.key] || []).map(t => t.toLowerCase());
      found = current.filter(i => !taken[i.id] && titles.indexOf(bare(i.title)) >= 0)[0];
    }
    if (found) taken[found.id] = true;
    return {key: c.key, id: found ? found.id : null, title: c.label + MULTIPLE, help: c.help || '',
            choices: c.options.slice()};
  });
  return {questions: questions, remove: current.filter(i => !taken[i.id]).map(i => i.id)};
}


// ------------------------------------------------------------------- an answer

function onAnswer(e) {
  const props = PropertiesService.getScriptProperties();
  const notify = (props.getProperty('NOTIFY') || '').trim();
  if (!notify) {
    console.log('The setting NOTIFY is empty, so no e-mail was sent.');
    return;
  }
  const response = e.response;
  const texts = {};
  const labels = [], unknown = [];
  response.getItemResponses().forEach(r => {
    const item = r.getItem(), value = r.getResponse();
    if (item.getType() === FormApp.ItemType.CHECKBOX) {
      const category = item.getTitle().replace(MULTIPLE, '').trim();
      const choices = item.asCheckboxItem().getChoices().map(c => c.getValue());
      (value || []).forEach(v => {
        labels.push([category, v]);
        if (choices.indexOf(v) < 0) unknown.push(category + ': ' + v);
      });
    } else {
      texts[item.getTitle()] = String(value == null ? '' : value).trim();
    }
  });
  const pick = titles => titles.map(t => texts[t]).filter(Boolean)[0] || '';
  const answer = {
    name: pick(Q.name), authors: pick(Q.authors), corresponding: pick(Q.corresponding),
    publishedAnswer: pick(Q.published), paper: pick(Q.paper), data: pick(Q.data),
    participants: pick(Q.participants), labels: labels, unknown: unknown,
    date: Utilities.formatDate(response.getTimestamp(), 'Europe/Berlin', 'yyyy-MM-dd'),
  };
  answer.published = /^yes/i.test(answer.publishedAnswer);
  answer.email = response.getRespondentEmail ? response.getRespondentEmail() : '';
  const seen = 'SEEN_' + response.getId();
  answer.changed = !!props.getProperty(seen);
  props.setProperty(seen, answer.date);
  answer.link = issueLink_(repo_(), answer);
  try { answer.sheet = 'https://docs.google.com/spreadsheets/d/' + FormApp.getActiveForm().getDestinationId(); }
  catch (err) { answer.sheet = ''; }
  const mail = mailText_(answer);
  MailApp.sendEmail(notify, mail.subject, mail.body);
}

// The link to the GitHub form "Add a study", filled in with an answer. GitHub fills in text
// fields from a link, but not dropdowns or checkboxes: the labels travel in the text field
// "Answers from the Google Form" (one "Category: answer" per line), and the person who opens
// the link chooses whether the study is published. Never in the link: the address of the
// person who sent the answer, and the links of a study that is not published yet.
function issueLink_(repo, a) {
  const fields = [
    ['title', 'Add a study: ' + a.name],
    ['name', a.name],
    ['authors', a.authors],
    ['corresponding_author', a.corresponding],
    ['participants', a.participants],
  ];
  if (a.published) fields.push(['paper', a.paper], ['data', a.data]);
  fields.push(['google_form', a.labels.map(l => l[0] + ': ' + l[1]).join('\n')]);
  fields.push(['notes', 'From the Google Form "Add your study to PredictIndex", answer of ' + a.date + '.']);
  return 'https://github.com/' + repo + '/issues/new?template=1-add-a-study.yml&' +
    fields.filter(f => f[1]).map(f => f[0] + '=' + encode_(f[1])).join('&');
}

// Every character but letters and digits written as %XX: a mail program that turns the
// address into a link stops at a final full stop or bracket otherwise (Gmail dropped the last
// "." of the link in the first test, 2026-11-24).
function encode_(text) {
  return encodeURIComponent(text).replace(/[!'()*.~_-]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase());
}

function mailText_(a) {
  const lines = [];
  lines.push(a.changed
    ? 'An answer sent earlier through the Google Form "Add your study to PredictIndex" has been changed.'
    : 'A study has been sent through the Google Form "Add your study to PredictIndex".', '');
  lines.push('Study: ' + (a.name || '(no name given)'));
  if (a.email) {
    lines.push('Sent by: ' + a.email + ' (this address is only in this e-mail; please do not copy it ' +
      'into GitHub, where everything is public)');
  }
  lines.push('Is the study published (or available as a preprint)? ' + (a.publishedAnswer || '(no answer)'), '');
  if (a.changed) {
    lines.push('If the study is on PredictIndex already, please make the changes with the GitHub form ' +
      'Change a study instead. The link below opens Add a study, which does not accept a name that is ' +
      'taken.', '');
  }
  lines.push('To add the study to PredictIndex:');
  lines.push('1. Open this link. It opens the GitHub form "Add a study", already filled in with the answers:');
  lines.push('   ' + a.link);
  lines.push('2. Under "Is the study published (or available as a preprint)?", choose ' +
    (a.published ? 'Yes' : 'Not yet') + '. GitHub cannot fill in this choice from a link. The labels are in ' +
    'the field "Answers from the Google Form"; they do not need to be ticked again.');
  lines.push('3. Check the answers: ' + (a.published
    ? 'that the paper link opens and belongs to this study, that the data link opens and is public, '
    : '') + 'that the authors are written as on the paper, and that the corresponding author is right. ' +
    'Anything can be corrected in the GitHub form before it is sent.');
  lines.push('4. Click Create. PredictIndex shows the study about a minute later, and the reply on GitHub ' +
    'says what has been added.', '');
  if (a.published && !a.paper) {
    lines.push('The answer says that the study is published, but gives no paper. GitHub needs the paper for a ' +
      'published study: please ask the person who sent the answer for its DOI or link and write it under Paper, ' +
      'or choose Not yet.', '');
  }
  if (!a.published && (a.paper || a.data)) {
    lines.push('The study is not published yet, so its paper and data links were left out of the GitHub ' +
      'form: links are only shown once a study is published.', '');
  }
  if (a.unknown.length) {
    lines.push('These answers are not among the options of PredictIndex: ' + a.unknown.join('; ') + '. ' +
      'They will be shown in the study\'s Details, but cannot be used as filters. To make one of them an ' +
      'option, first use the GitHub form Change the options.', '');
  }
  lines.push('If the study should not be added, nothing needs to be done.');
  if (a.sheet) lines.push('All answers: ' + a.sheet);
  return {
    subject: 'PredictIndex: ' + (a.changed ? 'changed answer' : 'new study') + ' from the Google Form: ' +
      (a.name || '(no name)'),
    body: lines.join('\n'),
  };
}


// ------------------------------------------------------------------ helpers

function repo_() {
  return (PropertiesService.getScriptProperties().getProperty('REPO') || DEFAULT_REPO).trim();
}

function findItem_(form, titles) {
  return form.getItems().filter(i => titles.indexOf(i.getTitle()) >= 0)[0] || null;
}
