# Looking after PredictIndex

*For the people who look after PredictIndex. The current version of this guide
is the file `MAINTENANCE.md` in the `predcommlab/network-datasets` repository on
GitHub; the PDF is a printed copy of it.*

## 1. How PredictIndex works

PredictIndex is the page **predcommlab.github.io/network-datasets**. It lists
studies with their labels (species, task paradigm, recording technique and so
on), and links to each study's paper and data. Visitors can search, filter by
the labels, and download the studies they see as an Excel table.

Everything on the page comes from the GitHub repository
**github.com/predcommlab/network-datasets**: one file for each study in the
folder `studies`, and the list of label options in the file `options.json`.

Changes are made with **forms on GitHub**. You fill in a form; an automatic
program reads it, changes the files, and puts the page online again. It
replies on the form's page with what it has done.

People who have no GitHub account add their study with the **Google Form "Add
your study to PredictIndex"**. Every answer arrives as an e-mail with a link;
you check the study and send it on to GitHub with a few clicks (section 4).

The repository is public. Everything written in it can be read by anyone,
including the forms and the replies to them.

## 2. How to make a change

1. Open **github.com/predcommlab/network-datasets/issues/new/choose**. You need
   to be signed in to GitHub. (The same page opens when you click **Issues** at
   the top of the repository and then the green **New issue** button.)
2. Choose the form that fits your change (see the table below).
3. Fill in the form and click **Create** at the bottom.
4. Within about a minute, a reply appears on the same page. It says what was
   changed and gives the link. PredictIndex shows the change about a minute
   later. When everything is done, the form is closed.
5. If the reply says that something is missing or wrong, nothing has been
   changed yet. Do one of these two things:
   - Change the form you sent: click the three dots at the top right of your
     form text, choose **Edit**, change it and click **Update comment**. The
     form is then read again.
   - Or fill in a new form with the correction (start again at step 1), and
     close the old one with the **Close issue** button at the bottom of its
     page.

## 3. The forms

| Form | Use it to | Who makes the change |
| ------------------ | ---------------------------------------------- | ------------------------------- |
| Add a study | add a new study, with its paper, its data and its labels. | automatic |
| Change a study | correct a study, add its paper and data once it is published, add or remove labels, or remove the study. | automatic (except Other changes) |
| Change the options | add, rename or remove one of the options that studies are labelled with. | automatic |
| Anything else | everything that none of the other forms covers. | the people who look after PredictIndex |

### Add a study

- **Study name** is the title of the study on PredictIndex. It has to be
  different from the names of all other studies.
- **Authors**: first and last names, separated by commas. The page writes them
  as "A, B & C".
- **Corresponding author**: PredictIndex can be filtered by this name.
- **Is the study published (or available as a preprint)?** If yes, give the
  paper under **Paper**: its DOI (for example 10.1038/s41598-024-59302-1) or a
  link to it. When it is given as a DOI, the paper's title is looked up
  automatically, and **Paper title** can stay empty. A preprint counts as
  published; PredictIndex marks it as a preprint.
- **Data**: the link to the data, for example on OSF or OpenNeuro. Leave it
  empty if the data is not public.
- If the study is **not published yet**, leave Paper and Data empty. Links of an
  unpublished study are never shown, so the form would not save them anyway.
  When the study is published, add them with the form Change a study.
- **Labels**: tick all that apply in each group; all are optional. If an option
  is missing, add it first with the form Change the options, or write it under
  Notes for the maintainers.
- Leave **Answers from the Google Form** empty. It is filled in automatically
  when the form is opened from the e-mail about a Google Form answer.

### Change a study

- Choose the study in the list at the top. Only the fields you fill in are
  changed; empty fields stay as they are.
- To empty a field, write a dash (-) into it. This works for Paper title, Paper,
  Data, Number of participants, Number of sessions, Acquisition and BIDS task
  label. Study name, Authors and Corresponding author can be changed, but not
  emptied.
- **Once a study is published**: choose Yes under "Is the study published (or
  available as a preprint)?" and give its Paper, and its Data if they are
  public. Choosing Not yet takes the study's links off the page again.
- **Labels**: choose labels under **Labels to add** and **Labels to remove**.
  You do not need to know the study's current labels for this. Some of the
  older studies show their owner's own description of a group in Details (for
  example "listening to syllable sequences"). When you change the labels of
  that group, the description is replaced by the labels.
- **Remove**: tick "Remove this study from PredictIndex".
- **Other changes**: anything else about the study. This part is not
  automatic; it goes to the people who look after PredictIndex.

### Change the options

- Choose the group (for example Stimulus properties) and what should change.
- **Add an option**: write it under New option. It is added at the end of the
  group. To add an option under another one, write both with a colon, for
  example "Clinical: dyslexia"; it then appears under Clinical.
- **Rename an option**: write the option as it is now, and the new wording.
  Every study that has the option gets the new wording. If the new wording is
  another existing option, the two become one.
- **Remove an option**: write the option as it is now. It is removed from every
  study that has it, and the reply lists those studies.
- An option cannot contain a comma.
- PredictIndex's filters and the GitHub forms follow within about a minute.
  The Google Form takes over the new options during the night.
- A new group, removing a whole group, or a new explanation for a group cannot
  be made with this form. Please use Anything else.

## 4. Studies from the Google Form

People without a GitHub account add their study with the Google Form "Add your
study to PredictIndex". Every answer is sent by e-mail to the people who look
after PredictIndex, with the subject **"PredictIndex: new study from the Google
Form: ..."**. The e-mail says what to do:

1. Open the link in the e-mail. It opens the GitHub form Add a study, already
   filled in with the answers. The labels are in the field "Answers from the
   Google Form"; they do not need to be ticked again.
2. Under "Is the study published (or available as a preprint)?", choose Yes or
   Not yet, as the e-mail says. GitHub cannot fill in this choice from a link.
3. Check the answers: that the paper link opens and belongs to this study, that
   the data link opens and is public, that the authors are written as on the
   paper, and that the corresponding author is right. Anything can be
   corrected in the form before it is sent.
4. Click **Create**. PredictIndex shows the study about a minute later.

Good to know:

- The e-mail contains the address of the person who sent the answer, so that
  you can ask them questions. **Never copy this address into GitHub**, where
  everything is public.
- Not every answer has to be added. If a study does not belong on PredictIndex,
  do nothing.
- If the answer says that the study is published but gives no paper, ask the
  person for its DOI, or choose Not yet.
- Answers that are not among the options (written under "Other" in the Google
  Form) are shown in the study's Details, but cannot be used as filters. To make
  one of them an option, use Change the options before adding the study.
- If someone changes an answer later, a second e-mail says so. If the study is
  on PredictIndex already, make the changes with Change a study.

## 5. Forms from people without access

Because the repository is public, anyone with a GitHub account can fill in a
form. Forms from people who do not have write access to the repository wait
for approval, and the reply on the form says so. (Anything else does not wait:
it goes straight to the people who look after PredictIndex.) Every form is
assigned to the people who look after PredictIndex, so GitHub notifies them.

- **To approve a form**: open it, check it, click **Labels** in the right-hand
  column and choose **approved**. The change is then made.
- **To turn a form down**: click **Close issue** at the bottom of its page,
  perhaps with a short comment.

## 6. Good to know

- **Not yet published** studies are listed without links ("Data will be shared
  after publication"). The program refuses links for them, so a link cannot
  appear on the page by mistake.
- **E-mail addresses**: a form that contains an e-mail address is not carried
  out; the reply asks to remove it. GitHub keeps every earlier version of a
  form: to delete the old version as well, click **edited** next to the date
  at the top of the form text, choose the earlier version, and choose
  **Delete revision from history**.
- **Trying out a form**: before clicking Create, add the label **test** in the
  right-hand column. The change is then saved separately and not published, and
  the reply says so.
- **When something goes wrong**, the reply says that there was a technical
  problem and that nothing has been changed, and the people who look after
  PredictIndex are mentioned. Edit the form once (Edit, then Update comment)
  to try again. If it fails again, the link after "Details" shows which step
  failed; please keep the form open and ask someone who knows GitHub's
  automatic processes (GitHub Actions) for help.
- **Undoing a change**: a removed study can be added again with Add a study.
  GitHub also keeps every earlier state of the repository (Commits, on the
  repository's main page), from which anything can be restored.

## 7. Changing a study's file yourself

This is rarely needed, for example to correct an owner's own description in
Details, which no form can change.

1. In the repository, open the folder `studies` and click the study's file.
2. Click the pencil (Edit this file) at the top right.
3. Change only the text between the quotation marks. Leave the quotation marks,
   commas and brackets as they are.
4. Click **Commit changes**, then **Commit changes** again in the window that
   opens. PredictIndex shows the change about a minute later.

If something in the file is wrong (for example a label that is not one of the
options), PredictIndex keeps showing the previous version, and GitHub sends you
an e-mail about a failed run of "Deploy". Open the file again and correct it,
or undo your change.

## 8. For administrators of the repository

**Who looks after PredictIndex** is set in one place: **Settings → Secrets and
variables → Actions → Variables → MAINTAINER** holds their GitHub user names,
separated by spaces. Every form is assigned to them, and they are mentioned
when something goes wrong. To hand PredictIndex over, change this one value.
(Only administrators of the repository see Settings.)

**E-mail for every new form**: click **Watch** at the top of the repository,
then **Custom**, tick **Issues** and click **Apply**.

**Access**: under **Settings → Collaborators and teams**. People with **Write**
access can use the forms directly and approve the forms of others;
administrators can also change the settings.

**The Google Form** belongs to the Google account of one of the people who look
after PredictIndex. A small program inside the form (in the form: the three
dots at the top right, Apps Script) sends the e-mails and takes over the
options every night. Its settings are under **Project Settings → Script
Properties**: **NOTIFY** holds the e-mail addresses that receive the e-mails,
separated by commas. The program's automatic runs belong to the Google account
that started them. So when the form gets a new owner:

1. The new owner opens Apps Script, chooses the function **setUp** at the top
   and clicks **Run**. The first time, Google asks for permission; allow it.
   (For a program of one's own, Google first shows a warning: click Advanced,
   then Go to ..., then Allow.)
2. The previous owner opens Apps Script, clicks **Triggers** (the clock symbol
   on the left) and deletes the two entries of their own account. Otherwise
   both accounts would send the e-mails.

The reference copy of this program is the file `google-form/predictindex_form.gs`
in the repository.

**Where things are** in the repository: `studies` (one file per study),
`options.json` (the label options), `index.html` (the page itself),
`.github/ISSUE_TEMPLATE` (the forms), `.github/workflows` and `.github/scripts`
(the automatic processes), `tests` (checks that run before every update of the
page), `google-form` (the Google Form's program). Changes to the page, the forms
or the processes are best made by someone familiar with them.

## 9. Please do not

- write e-mail addresses, or links that a study's authors do not want public
  yet, into a form or anywhere else in the repository;
- change the folders `.github`, `tests` or `google-form`, or the file
  `index.html`, unless you know what the change does. They hold the page and the
  automatic processes.
