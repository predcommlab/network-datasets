#!/usr/bin/env python3
"""PredictIndex: the page's data, the checks it has to pass, and the forms.

The repository holds the data of https://predcommlab.github.io/network-datasets/:

  options.json        the label options of every category, the only place
                      they are written down
  studies/<id>.json   one file per study

  predictindex.py build [--root DIR] [--out FILE]
      checks options.json and every study file, then writes studies.js, the
      file the page reads (OPTIONS and STUDIES). If anything is wrong, it lists
      every problem, writes nothing and exits with status 1.
  predictindex.py check [--root DIR]
      only the checks.
  predictindex.py form <issue number> [--root DIR] [--issue-file JSON]
      carries out a form (Issues > New issue in this repository), see "The
      forms" below; used by the Forms workflow.
  predictindex.py sync [--root DIR]
      writes the generated parts of the forms in .github/ISSUE_TEMPLATE/ (the
      label questions, the list of studies, the list of categories) from the
      data as it is now.

What the checks enforce:
  - every label of a study is one of the options of its category;
  - study names are unique;
  - a study that is not published has no paper and no data link, so an
    outward link can only reach the page once the study is published;
  - links are web addresses, and a paper is a DOI or a link;
  - no "@" anywhere, so that no e-mail address can reach the public page.

The forms (label "form: <kind>", set by the template):
  form: add      Add a study           a new file in studies/
  form: change   Change a study        the fields filled in, labels added or
                                       removed, or the study removed
  form: options  Change the options    an option added, renamed or removed, in
                                       options.json and in every study
  form: other    Anything else         passed on to the people in MAINTAINER

For the workflow, in $GITHUB_OUTPUT:
  result   done        data changed; reply, then close the issue
           partial     data changed, a part is left for a person; reply
           waiting     nothing to do automatically yet; reply
           needs-info  nothing changed; the reply says what to correct
           skip        nothing to do (a closed issue, not a form, a label
                       other than approved)
           error       a technical problem; the reply says so
  summary  one line for the commit message
The reply goes to the file named by $REPLY_FILE.

Python standard library only.
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]  # the repository: .github/scripts/ is two levels down
OPTIONS_FILE = "options.json"
STUDIES_DIR = "studies"
PAGE_DATA = "studies.js"

# The fields of a study file, in the order they are written.
FIELDS = ["name", "paperTitle", "authors", "correspondingAuthor", "published", "paper",
          "dataUrl", "participants", "sessions", "acquisition", "bidsTaskLabels", "added",
          "labels", "descriptions"]
REQUIRED = ["name", "authors", "correspondingAuthor", "published", "added"]
TEXT_FIELDS = [f for f in FIELDS if f not in ("published", "labels", "descriptions")]
CATEGORY_FIELDS = ["key", "label", "help", "filter", "options"]
RESERVED_KEYS = {"status", "owner", "q"}  # the page's own URL parameters

DOI = re.compile(r"10\.\d{4,9}/\S+")
FILE_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\.json")
KEY = re.compile(r"[a-z][A-Za-z]*")

# A paper counts as a preprint when its DOI has the prefix of a preprint
# server, or its address is one of a preprint server.
PREPRINT_DOIS = ("10.1101/", "10.31234/", "10.31219/", "10.48550/", "10.21203/",
                 "10.2139/", "10.20944/")
PREPRINT_HOSTS = ("biorxiv.org", "medrxiv.org", "psyarxiv.com", "arxiv.org",
                  "researchsquare.com", "ssrn.com", "preprints.org")


# ------------------------------------------------------------ small helpers

def one_line(text):
    return " ".join(str(text or "").split())


def is_web(text):
    """An http or https address with a host name, without spaces."""
    if not isinstance(text, str) or re.search(r"\s", text):
        return False
    p = urlparse(text)
    return p.scheme in ("http", "https") and "." in p.netloc


def is_date(text):
    try:
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", text)) and bool(dt.date.fromisoformat(text))
    except ValueError:
        return False


def strings(value):
    """Every piece of text in a JSON value, the names of entries included."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)
    elif isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from strings(v)


def load_json(path, problems, label):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        problems.append(f"{label}: this is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg}).")
    except (OSError, UnicodeDecodeError) as e:
        problems.append(f"{label}: the file cannot be read ({e}).")
    return None


def dump_json(value):
    """How every data file is written: two spaces of indentation, letters such
    as ä written as they are, a line break at the end."""
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


# --------------------------------------------------------------- the checks

def check_options(options):
    """Problems in options.json, as sentences."""
    where0 = OPTIONS_FILE
    if not (isinstance(options, dict) and list(options) == ["categories"]
            and isinstance(options["categories"], list) and options["categories"]):
        return [f'{where0}: it has to contain one entry, "categories", a list of categories.']
    problems, keys, labels = [], set(), set()
    for i, c in enumerate(options["categories"], 1):
        if not isinstance(c, dict):
            problems.append(f"{where0}, category {i}: it has to be an object ({{...}}).")
            continue
        key = c.get("key")
        where = f"{where0}, category {i}" + (f' ("{key}")' if isinstance(key, str) else "")
        for k in c:
            if k not in CATEGORY_FIELDS:
                problems.append(f'{where}: unknown entry "{k}". Possible entries: {", ".join(CATEGORY_FIELDS)}.')
        if not isinstance(key, str) or not KEY.fullmatch(key):
            problems.append(f'{where}: "key" has to be one word of letters that starts with a small '
                            'letter, for example stimulusQuality.')
        elif key in RESERVED_KEYS:
            problems.append(f'{where}: the key "{key}" is used by the page itself; please choose another.')
        elif key in keys:
            problems.append(f'{where}: the key "{key}" is used twice.')
        else:
            keys.add(key)
        label = c.get("label")
        if not isinstance(label, str) or not label.strip():
            problems.append(f'{where}: "label" is missing.')
        elif "," in label:
            problems.append(f'{where}: the label "{label}" contains a comma, which is not allowed.')
        elif label.casefold() in labels:
            problems.append(f'{where}: the label "{label}" is used twice.')
        else:
            labels.add(label.casefold())
        if "help" in c and not (isinstance(c["help"], str) and c["help"].strip()):
            problems.append(f'{where}: "help" has to be a piece of text.')
        if "filter" in c and not isinstance(c["filter"], bool):
            problems.append(f'{where}: "filter" has to be true or false, without quotes.')
        opts = c.get("options")
        if not isinstance(opts, list) or not opts:
            problems.append(f'{where}: "options" has to be a list with at least one option.')
            continue
        seen = set()
        for o in opts:
            if not isinstance(o, str) or not o.strip():
                problems.append(f"{where}: every option has to be a piece of text.")
            elif o != one_line(o):
                problems.append(f'{where}: the option "{o}" has spaces at its start or end, or a line break.')
            elif "," in o:
                problems.append(f'{where}: the option "{o}" contains a comma, which is not allowed '
                                '(GitHub separates the options chosen in a form with commas).')
            elif o.casefold() in seen:
                problems.append(f'{where}: the option "{o}" is listed twice.')
            else:
                seen.add(o.casefold())
    if any("@" in s for s in strings(options)):
        problems.append(f'{where0}: contains "@". No e-mail addresses may be written into the data.')
    return problems


def check_study(where, data, categories):
    """Problems in one study file, as sentences. `categories` maps each key of
    options.json to its category."""
    problems = []

    def bad(message):
        problems.append(f"{where}: {message}")

    if not isinstance(data, dict):
        bad("it has to be an object ({...}).")
        return problems
    for k in data:
        if k not in FIELDS:
            bad(f'unknown field "{k}". The fields are: {", ".join(FIELDS)}.')
    for k in REQUIRED:
        if data.get(k) in (None, ""):
            bad(f'"{k}" is missing.')
    for k in TEXT_FIELDS:
        if k in data and not isinstance(data[k], str):
            bad(f'"{k}" has to be a piece of text in quotes.')
    if "published" in data and not isinstance(data["published"], bool):
        bad('"published" has to be true or false, without quotes.')
    text = lambda k: data[k].strip() if isinstance(data.get(k), str) else ""
    if text("added") and not is_date(text("added")):
        bad(f'"added" has to be a date written as YYYY-MM-DD, for example 2026-11-24, not "{text("added")}".')
    paper, data_url = text("paper"), text("dataUrl")
    if paper and not (DOI.fullmatch(paper) or is_web(paper)):
        bad(f'"paper" has to be a DOI (10.xxxx/...) or a web address that starts with https://, not "{paper}".')
    if data_url and not is_web(data_url):
        bad(f'"dataUrl" has to be a web address that starts with https://, not "{data_url}".')
    if data.get("published") is False and (paper or data_url):
        bad('the study is not published, so it may not have a paper or data link yet: links are only '
            'shown once a study is published. Remove "paper" and "dataUrl", or set "published" to true.')

    labels = data.get("labels", {})
    if not isinstance(labels, dict):
        bad('"labels" has to be an object ({...}).')
        labels = {}
    for key, values in labels.items():
        if key not in categories:
            bad(f'labels: "{key}" is not a category of {OPTIONS_FILE}.')
            continue
        cat = categories[key]
        if not (isinstance(values, list) and values and all(isinstance(v, str) for v in values)):
            bad(f'labels: "{key}" has to be a list of options, for example ["{cat["options"][0]}"].')
            continue
        for v in values:
            if v not in cat["options"]:
                bad(f'labels: "{v}" is not one of the options of {cat["label"]}. '
                    f'The options are: {", ".join(cat["options"])}.')
        if len(set(values)) != len(values):
            bad(f'labels: an option of {cat["label"]} is listed twice.')
    descriptions = data.get("descriptions", {})
    if not isinstance(descriptions, dict):
        bad('"descriptions" has to be an object ({...}).')
        descriptions = {}
    for key, value in descriptions.items():
        if key not in categories:
            bad(f'descriptions: "{key}" is not a category of {OPTIONS_FILE}.')
        elif not (isinstance(value, str) and value.strip()):
            bad(f'descriptions: "{key}" has to be a piece of text.')
    if any("@" in s for s in strings(data)):
        bad('contains "@". No e-mail addresses may be written into the data.')
    return problems


def load(root):
    """Reads and checks all data. Returns (problems, options, studies), where
    studies is a list of (id, data); the id is the file name without .json."""
    root = Path(root)
    problems = []
    options = load_json(root / OPTIONS_FILE, problems, OPTIONS_FILE)
    if options is not None:
        problems += check_options(options)
    categories = {c["key"]: c for c in options["categories"]} if options is not None and not problems else None
    studies = []
    folder = root / STUDIES_DIR
    if not folder.is_dir():
        problems.append(f"The folder {STUDIES_DIR}/ is missing.")
        return problems, options, studies
    for path in sorted(folder.iterdir()):
        if path.name.startswith("."):
            continue  # files such as .DS_Store, which macOS leaves behind
        where = f"{STUDIES_DIR}/{path.name}"
        if path.is_dir() or path.suffix != ".json":
            problems.append(f"{where}: only .json files belong in the folder {STUDIES_DIR}/.")
            continue
        if not FILE_NAME.fullmatch(path.name):
            problems.append(f"{where}: a file name may only contain small letters, digits and hyphens, "
                            "for example my-study.json.")
        data = load_json(path, problems, where)
        if data is None:
            continue
        if categories is not None:
            problems += check_study(where, data, categories)
        studies.append((path.stem, data))
    names = {}
    for sid, data in studies:
        name = data.get("name") if isinstance(data, dict) else None
        if isinstance(name, str) and name.strip():
            names.setdefault(one_line(name).casefold(), []).append(sid)
    for ids in names.values():
        if len(ids) > 1:
            problems.append("These studies have the same name; every study needs a name of its own: "
                            + ", ".join(f"{STUDIES_DIR}/{i}.json" for i in ids) + ".")
    return problems, options, studies


# ------------------------------------------------------ changing the options

def category(options, key):
    """The category of options.json with this key."""
    for c in options["categories"]:
        if c["key"] == key:
            return c
    raise KeyError(key)


def same_text(a, b):
    return one_line(a).casefold() == one_line(b).casefold()


def add_option(options, key, option, after=None):
    """Adds an option to a category: after the option `after`, or at the end."""
    opts = category(options, key)["options"]
    opts.insert(opts.index(after) + 1 if after in opts else len(opts), option)


def rename_option(options, studies, key, old, new):
    """Renames an option in options.json and in every study that has it; if
    `new` is an option already, the two become one. A description of the
    category that only repeats the old option becomes the new one. Returns the
    ids of the studies changed. `studies` is a list of (id, data)."""
    opts = category(options, key)["options"]
    i = opts.index(old)
    if new in opts:
        opts.pop(i)
    else:
        opts[i] = new
    touched = []
    for sid, data in studies:
        labels, texts = data.setdefault("labels", {}), data.setdefault("descriptions", {})
        changed = False
        if old in labels.get(key, []):
            labels[key] = list(dict.fromkeys(new if v == old else v for v in labels[key]))
            changed = True
        if key in texts and same_text(texts[key], old):
            texts[key] = new
            changed = True
        if changed:
            touched.append(sid)
    return touched


def remove_option(options, studies, key, option):
    """Removes an option from options.json and from every study that has it. A
    description of the category that only repeats the option goes as well.
    Returns the ids of the studies changed."""
    category(options, key)["options"].remove(option)
    touched = []
    for sid, data in studies:
        labels, texts = data.setdefault("labels", {}), data.setdefault("descriptions", {})
        changed = False
        if option in labels.get(key, []):
            labels[key] = [v for v in labels[key] if v != option]
            if not labels[key]:
                del labels[key]
            changed = True
        if key in texts and same_text(texts[key], option):
            del texts[key]
            changed = True
        if changed:
            touched.append(sid)
    return touched


def canonical_options(options):
    """options.json as it is written: each category's entries in the order of
    CATEGORY_FIELDS."""
    return {"categories": [{k: c[k] for k in CATEGORY_FIELDS if k in c} for c in options["categories"]]}


def save(root, options, studies, ids=None):
    """Writes options.json and the study files: all of them, or those whose id
    is in `ids`."""
    root = Path(root)
    (root / OPTIONS_FILE).write_text(dump_json(canonical_options(options)), encoding="utf-8")
    order = [c["key"] for c in options["categories"]]
    for sid, data in studies:
        if ids is None or sid in ids:
            (root / STUDIES_DIR / f"{sid}.json").write_text(dump_json(canonical_study(data, order)),
                                                            encoding="utf-8")


# ------------------------------------------------------------- the writing

def canonical_study(data, order):
    """A study as it is written to its file: the fields in the order of FIELDS,
    labels and descriptions in the order of the categories (`order`, a list of
    keys), text on one line, nothing empty."""
    out = {}
    for k in FIELDS:
        v = data.get(k)
        if k == "published":
            if isinstance(v, bool):
                out[k] = v
        elif k == "labels":
            labels = {key: [one_line(x) for x in v] for key, v in (v or {}).items() if v}
            if labels:
                out[k] = {key: labels[key] for key in order if key in labels}
        elif k == "descriptions":
            texts = {key: one_line(x) for key, x in (v or {}).items() if one_line(x)}
            if texts:
                out[k] = {key: texts[key] for key in order if key in texts}
        elif one_line(v):
            out[k] = one_line(v)
    return out


def paper_link(paper):
    """(address to open, DOI or None) for a study's paper."""
    if DOI.fullmatch(paper):
        return "https://doi.org/" + paper, paper
    return paper, None


def is_preprint(paper):
    if DOI.fullmatch(paper):
        return paper.lower().startswith(PREPRINT_DOIS)
    p = urlparse(paper)
    host = p.netloc.lower().removeprefix("www.")
    if host in ("doi.org", "dx.doi.org"):
        return p.path.lstrip("/").lower().startswith(PREPRINT_DOIS)
    if host == "osf.io":
        return p.path.startswith("/preprints")
    return any(host == h or host.endswith("." + h) for h in PREPRINT_HOSTS)


def page_study(sid, data, order):
    """A study as the page reads it: the file's fields, its id, and the paper
    as a link (paperLink), its DOI if it has one (paperDoi) and whether it is
    a preprint."""
    s = canonical_study(data, order)
    out = {"id": sid}
    for k in FIELDS:
        if k not in s:
            continue
        if k == "paper":
            link, doi = paper_link(s["paper"])
            out["paperLink"] = link
            if doi:
                out["paperDoi"] = doi
            if is_preprint(s["paper"]):
                out["preprint"] = True
        else:
            out[k] = s[k]
    out.setdefault("labels", {})
    out.setdefault("descriptions", {})
    return out


def page_order(studies):
    """Newest first (the date a study was added), alphabetical within a day."""
    by_name = sorted(studies, key=lambda s: s["name"].casefold())
    return sorted(by_name, key=lambda s: s["added"], reverse=True)


def page_data(options, studies):
    order = [c["key"] for c in options["categories"]]
    listed = page_order([page_study(sid, data, order) for sid, data in studies])
    return ("// PredictIndex data: GENERATED from options.json and the files in studies/ by\n"
            "// .github/scripts/predictindex.py build. Do not edit this file; change the\n"
            "// data instead, and the next build writes it again.\n\n"
            "const OPTIONS = " + json.dumps(options, ensure_ascii=False, indent=1) + ";\n\n"
            "const STUDIES = " + json.dumps(listed, ensure_ascii=False, indent=1) + ";\n")


def build(root, out=None):
    """Checks the data and writes studies.js. Returns the problems found; if
    there are any, nothing is written."""
    root = Path(root)
    problems, options, studies = load(root)
    if problems:
        return problems
    text = page_data(options, studies)
    Path(out or root / PAGE_DATA).write_text(text, encoding="utf-8")
    return []


# ----------------------------------------------------------------- the forms
#
# Maintainers change PredictIndex by filling in a form: Issues > New issue in
# this repository. The Forms workflow runs `predictindex.py form <number>` on
# the issue; this changes the files in studies/ or options.json and leaves the
# reply. The workflow commits the change (publish.sh), starts the deploy,
# replies and closes the issue.

REPO = "predcommlab/network-datasets"
def site():
    """The page's address: the GitHub Pages address of the repository the
    workflow runs in (https://predcommlab.github.io/network-datasets/ for
    predcommlab/network-datasets), unless the variable SITE_URL names another."""
    if os.environ.get("SITE_URL"):
        return os.environ["SITE_URL"].rstrip("/") + "/"
    owner, _, name = os.environ.get("GITHUB_REPOSITORY", REPO).partition("/")
    return f"https://{owner.lower()}.github.io/{name}/"
TEMPLATES = Path(".github") / "ISSUE_TEMPLATE"
USER_AGENT = "PredictIndex forms (+https://github.com/predcommlab/network-datasets)"
NO_ANSWER = {"", "_no response_", "none"}
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CLEAR = {"-", "–", "—"}  # a dash in a field of Change a study empties the field
MULTIPLE = "(multiple selections possible)"

# The questions of the forms as they appear in an issue: the labels in the
# templates in .github/ISSUE_TEMPLATE/. The two have to agree.
Q = {
    "name": "Study name",
    "paper_title": "Paper title",
    "authors": "Authors",
    "corresponding": "Corresponding author",
    "published": "Is the study published (or available as a preprint)?",
    "paper": "Paper",
    "data": "Data",
    "participants": "Number of participants",
    "sessions": "Number of sessions",
    "acquisition": "Acquisition",
    "bids": "BIDS task label",
    "google": "Answers from the Google Form",
    "notes": "Notes for the maintainers",
    "study": "Study",
    "remove": "Remove",
    "add_labels": "Labels to add",
    "remove_labels": "Labels to remove",
    "other": "Other changes",
    "category": "Category",
    "action": "What should change?",
    "current": "Option as it is now",
    "new": "New option",
}
# The text fields of Change a study and the fields of a study file they change.
CHANGE_TEXT = [("name", "name"), ("paper_title", "paperTitle"), ("authors", "authors"),
               ("corresponding", "correspondingAuthor"), ("participants", "participants"),
               ("sessions", "sessions"), ("acquisition", "acquisition"), ("bids", "bidsTaskLabels")]
CLEARABLE = {"paperTitle", "participants", "sessions", "acquisition", "bidsTaskLabels", "paper", "dataUrl"}
FIELD_NAMES = {"name": "Study name", "paperTitle": "Paper title", "authors": "Authors",
               "correspondingAuthor": "Corresponding author", "participants": "Number of participants",
               "sessions": "Number of sessions", "acquisition": "Acquisition",
               "bidsTaskLabels": "BIDS task label", "paper": "Paper", "dataUrl": "Data"}


class Missing(Exception):
    """Something the person who sent the form has to add or correct; the
    message says what."""


def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def fields(body):
    """The answers of an issue form, as {question: text}."""
    answers = {}
    body = (body or "").replace("\r\n", "\n")
    for label, text in re.findall(r"^### (.+?)[ \t]*\n(.*?)(?=^### |\Z)", body, re.M | re.S):
        text = text.strip()
        answers[label.strip()] = "" if text.lower() in NO_ANSWER else text
    return answers


def ticked(text):
    """The options ticked in a group of checkboxes ("- [X] Human")."""
    return [m.group(1).strip() for m in re.finditer(r"^\s*-\s*\[[xX]\]\s*(.+?)\s*$", text or "", re.M)]


def chosen(text):
    """The options chosen in a dropdown that allows several; GitHub joins them
    with ", ", and options contain no comma."""
    return [p.strip() for p in one_line(text).split(", ") if p.strip()]


def maintainers():
    """The GitHub user names in the repository variable MAINTAINER."""
    return [w.lstrip("@") for w in re.split(r"[\s,]+", os.environ.get("MAINTAINER", "")) if w.strip("@")]


def the_maintainers():
    who = ", ".join("@" + w for w in maintainers())
    return f"the people who look after PredictIndex ({who})" if who else "the people who look after PredictIndex"


def passed_on():
    return f"This has been passed on to {the_maintainers()}, who make the change and reply here."


def awaiting_approval():
    return ("This form takes effect once it has been approved: one of "
            f"{the_maintainers()} adds the label approved on this page (Labels, on the right). "
            "Until then nothing on PredictIndex changes.")


def technical_problem():
    run = os.environ.get("RUN_URL", "")
    who = the_maintainers()
    return ("PredictIndex could not be updated because of a technical problem, so nothing has been changed. "
            f"{who[0].upper() + who[1:]} have been notified." + (f" Details: {run}" if run else ""))


def edit_hint(repo):
    return ("To correct it, do one of these two things:\n"
            "- Change this form: click the three dots at the top right of your form text on this page, "
            "choose Edit, change it and click Update comment. The form is then read again.\n"
            f"- Or fill in a new form with the correction (https://github.com/{repo}/issues/new/choose), "
            "and close this one with the Close issue button at the bottom of this page.")


def online(name=None):
    link = site() + ("?q=" + urllib.parse.quote_plus(name) if name else "")
    return f"PredictIndex shows the change in about a minute: {link}"


def may_publish(login, repo):
    """Forms from people with write access take effect at once; everyone
    else's wait for the label approved."""
    if not login:
        return False
    try:
        level = gh("api", f"repos/{repo}/collaborators/{login}/permission", "--jq", ".permission").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return level in ("admin", "maintain", "write")


def today():
    return dt.datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat()


def lookup_doi(doi):
    """(found, title) of a DOI, from doi.org: it answers for the DOIs of every
    registration agency (Crossref, DataCite, ...). found is None when doi.org
    could not be asked."""
    request = urllib.request.Request("https://doi.org/" + urllib.parse.quote(doi, safe="/"), headers={
        "Accept": "application/vnd.citationstyles.csl+json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            record = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return (False, "") if e.code == 404 else (None, "")
    except (OSError, ValueError):
        return None, ""
    title = record.get("title") if isinstance(record, dict) else ""
    if isinstance(title, list):
        title = title[0] if title else ""
    return True, str(title or "")


def clean_title(title):
    """A registered title as plain text: some publishers register it with HTML
    tags (<i>) and entities (&amp;)."""
    return one_line(html.unescape(re.sub(r"<[^>]+>", "", title or "")))


def link_status(url):
    """The HTTP status a link answers with, or None if it could not be reached."""
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue  # some sites refuse HEAD but answer GET
            return e.code
        except (OSError, ValueError):
            return None
    return None


def plain(text, question):
    """A one-line answer; "@" is refused, since no e-mail address may be written
    into the data."""
    value = one_line(text)
    if "@" in value:
        raise Missing(f"{question} may not contain the character @.")
    return value


def yes_no(text):
    answer = one_line(text).lower()
    return True if answer == "yes" else False if answer.startswith("not yet") else None


def paper_value(text):
    """A paper as a bare DOI (written as 10.xxxx/..., doi:10.xxxx/... or as a
    doi.org link) or as a link."""
    value = one_line(text)
    if not value:
        return ""
    value = re.sub(r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)", "", value, flags=re.I)
    if DOI.fullmatch(value) or is_web(value):
        return value
    raise Missing(f'"{one_line(text)}" under Paper is neither a DOI (such as 10.1038/s41598-024-59302-1) '
                  "nor a link that starts with https://.")


def data_value(text):
    value = one_line(text)
    if value and not is_web(value):
        raise Missing(f'"{value}" under Data is not a link. Please give the address of the data, starting with https://.')
    return value


INITIALS = re.compile(r"(?:[A-Z]\.?\s*-?\s*)+")


def house_authors(text):
    """Authors as the page writes them: "A, B & C". A list written as
    surnames with initials ("Becker, J., Korn, C.") is kept as it is."""
    value = plain(text, Q["authors"])
    parts = [p for p in re.split(r"\s*;\s*|\s*,\s*|\s+&\s+|\s+and\s+", value) if p.strip()]
    if not parts or any(INITIALS.fullmatch(p) for p in parts):
        return value
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " & " + parts[-1]


def new_id(name, taken):
    """A file name for a new study, made from its name."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    if len(s) > 60:
        s = s[:60]
        s = s.rsplit("-", 1)[0] if "-" in s[20:] else s
    s = s.strip("-") or "study"
    sid, n = s, 2
    while sid in taken:
        sid, n = f"{s}-{n}", n + 1
    return sid


def category_by_label(options, label):
    label = re.sub(r"\s*" + re.escape(MULTIPLE) + r"\s*$", "", one_line(label), flags=re.I)
    return next((c for c in options["categories"] if c["label"].casefold() == label.casefold()), None)


def option_in(cat, text):
    """The option of a category that `text` names, whatever its capitals."""
    return next((o for o in cat["options"] if o.casefold() == one_line(text).casefold()), None)


def parent_of(option):
    i = option.find(": ")
    return option[:i] if i > 0 else None


def label_choice(options, item):
    """(category, option) for an entry "Category: option" of the dropdowns in
    Change a study."""
    head, _, rest = item.partition(": ")
    cat = category_by_label(options, head)
    option = option_in(cat, rest) if cat else None
    if not option:
        raise Missing(f'"{item}" is no longer one of the labels. Please choose it again from the list in a new form; '
                      "the list is updated after every change.")
    return cat, option


def paper_checks(paper, title, data_url, notes):
    """Looks the paper's DOI up (it has to exist; its title is taken when none
    was given) and tries the data link (a warning only). Returns the title."""
    if paper and DOI.fullmatch(paper):
        found, registered = lookup_doi(paper)
        registered = clean_title(registered)
        if found is False:
            raise Missing(f"The DOI {paper} could not be found at doi.org. Please check it, "
                          "or give a link to the paper under Paper instead.")
        if found is None:
            notes.append(f"The DOI {paper} could not be checked just now, as doi.org did not answer; it was saved as given.")
        elif registered and not title:
            title = registered
            notes.append(f"The paper's title was taken from doi.org: {title}")
    if data_url:
        status = link_status(data_url)
        if status is None:
            notes.append("The data link could not be checked just now; it was saved as given.")
        elif status >= 400:
            notes.append(f"The data link answers with an error (status {status}), so it may not be public yet. "
                         "It was saved anyway; please check that it opens, and correct it with the form Change a "
                         "study if needed.")
    return title


def labels_from_add(answers, options, notes):
    """The labels ticked in Add a study, plus the lines of Answers from the
    Google Form ("Category: answer", one per line). An answer that is not an
    option keeps the category's answers as the study's own description of it,
    shown in Details."""
    labels, texts, written = {}, {}, {}
    for cat in options["categories"]:
        for option in ticked(answers.get(cat["label"], "")):
            known = option_in(cat, option)
            if not known:
                raise Missing(f'"{option}" is no longer an option of {cat["label"]}. Please open the form again; '
                              "it shows the current options.")
            labels.setdefault(cat["key"], [])
            if known not in labels[cat["key"]]:
                labels[cat["key"]].append(known)
    for line in (answers.get(Q["google"]) or "").splitlines():
        line = line.strip().lstrip("-*• ").strip()
        if not line:
            continue
        head, sep, value = line.partition(": ")
        cat = category_by_label(options, head) if sep else None
        if not cat or not one_line(value):
            notes.append(f'The line "{line}" under {Q["google"]} was left out, as it does not name one of the '
                         "categories of PredictIndex and an answer.")
            continue
        if "@" in value:
            raise Missing(f"{Q['google']} may not contain the character @.")
        written.setdefault(cat["key"], []).append(one_line(value))
    for key, values in written.items():
        cat = category(options, key)
        for v in values:
            known = option_in(cat, v)
            if known and known not in labels.setdefault(key, []):
                labels[key].append(known)
        if not labels.get(key):
            labels.pop(key, None)
        unknown = [v for v in values if not option_in(cat, v)]
        if unknown:
            texts[key] = ", ".join(dict.fromkeys(values))
            notes.append(f'{", ".join(chr(34) + v + chr(34) for v in unknown)} '
                         f'{"is not an option" if len(unknown) == 1 else "are not options"} of {cat["label"]}, '
                         "so the answer is shown in the study's Details but cannot be used as a filter. To make it "
                         "an option, use the form Change the options, then add it to the study with the form "
                         "Change a study.")
    return labels, texts


def verified(root):
    problems, options, studies = load(root)
    if problems:
        raise RuntimeError("The data does not pass the checks: " + " ".join(problems))
    return options, studies


def add_study(answers, root, options, studies):
    notes = []
    name = plain(answers.get(Q["name"]), Q["name"])
    authors = house_authors(answers.get(Q["authors"]))
    corresponding = plain(answers.get(Q["corresponding"]), Q["corresponding"])
    missing = [q for q, v in ((Q["name"], name), (Q["authors"], authors), (Q["corresponding"], corresponding)) if not v]
    if missing:
        raise Missing("Please fill in: " + ", ".join(missing) + ".")
    if any(same_text(d.get("name"), name) for _, d in studies):
        raise Missing(f'There is already a study called "{name}" on PredictIndex. To change it, please use the '
                      "form Change a study.")
    published = yes_no(answers.get(Q["published"]))
    if published is None:
        raise Missing(f'Please choose Yes or Not yet under "{Q["published"]}"')
    paper, data_url = paper_value(answers.get(Q["paper"])), data_value(answers.get(Q["data"]))
    title = plain(answers.get(Q["paper_title"]), Q["paper_title"])
    study = {"name": name, "authors": authors, "correspondingAuthor": corresponding, "published": published,
             "participants": plain(answers.get(Q["participants"]), Q["participants"]),
             "sessions": plain(answers.get(Q["sessions"]), Q["sessions"]), "added": today()}
    if published:
        if not paper:
            raise Missing("A published study needs its paper: please give its DOI or a link under Paper. "
                          "If the study is not published yet, please choose Not yet.")
        title = paper_checks(paper, title, data_url, notes)
        study.update(paper=paper, dataUrl=data_url)
    elif paper or data_url:
        notes.append("The study is not published yet, so the links under Paper and Data were not saved: links "
                     "are only shown once a study is published. When it is, please use the form Change a study, "
                     "choose Yes under the question whether it is published, and give the links there.")
    study["paperTitle"] = title
    study["labels"], study["descriptions"] = labels_from_add(answers, options, notes)
    sid = new_id(name, {s for s, _ in studies})
    order = [c["key"] for c in options["categories"]]
    (Path(root) / STUDIES_DIR / f"{sid}.json").write_text(dump_json(canonical_study(study, order)), encoding="utf-8")
    verified(root)
    reply = [f"Added to PredictIndex: {name}.", online(name)] + notes
    reply.append("To change this study later, please use the form Change a study.")
    return "done", f"add {name}", reply


def change_study(answers, root, options, studies):
    wanted = one_line(answers.get(Q["study"]))
    if not wanted:
        raise Missing("Please choose the study.")
    match = [(sid, d) for sid, d in studies if same_text(d.get("name"), wanted)]
    if not match:
        raise Missing(f'There is no study called "{wanted}" on PredictIndex any more. Please choose it again in a '
                      "new form; the list is updated after every change.")
    sid, data = match[0]
    path = Path(root) / STUDIES_DIR / f"{sid}.json"
    other = (answers.get(Q["other"]) or "").strip()
    filled = [q for k, q in Q.items() if k not in ("study", "remove", "other") and one_line(answers.get(q))]
    if ticked(answers.get(Q["remove"])):
        path.unlink()
        verified(root)
        reply = [f"Removed from PredictIndex: {data['name']}.",
                 "If this was a mistake, the study can be restored from the history of this repository; please "
                 "ask with the form Anything else.", online()]
        if filled or other:
            reply.insert(1, "The other fields of the form were not needed, since the study is removed.")
        return "done", f"remove {data['name']}", reply

    changes, notes = [], []
    for question, field in CHANGE_TEXT:
        raw = one_line(answers.get(Q[question]))
        if not raw:
            continue
        if raw in CLEAR:
            if field not in CLEARABLE:
                raise Missing(f"{Q[question]} cannot be emptied: a study always has one.")
            if data.pop(field, None):
                changes.append(f"{FIELD_NAMES[field]}: removed")
            continue
        value = house_authors(raw) if field == "authors" else plain(raw, Q[question])
        if field == "name" and any(same_text(d.get("name"), value) for s, d in studies if s != sid):
            raise Missing(f'There is already another study called "{value}" on PredictIndex.')
        if value != data.get(field):
            data[field] = value
            changes.append(f"{FIELD_NAMES[field]}: {value}")

    raw_paper, raw_data = one_line(answers.get(Q["paper"])), one_line(answers.get(Q["data"]))
    new_paper = None if not raw_paper else "" if raw_paper in CLEAR else paper_value(raw_paper)
    new_data = None if not raw_data else "" if raw_data in CLEAR else data_value(raw_data)
    now_published = yes_no(answers.get(Q["published"]))
    if now_published is not None and now_published != data["published"]:
        data["published"] = now_published
        changes.append("Published: " + ("yes" if now_published else "not yet"))
    if data["published"]:
        for field, new in (("paper", new_paper), ("dataUrl", new_data)):
            if new is not None and new != data.get(field, ""):
                if new:
                    data[field] = new
                else:
                    data.pop(field, None)
                changes.append(f"{FIELD_NAMES[field]}: {new or 'removed'}")
        if not data.get("paper"):
            raise Missing("A published study needs its paper: please give its DOI or a link under Paper. "
                          "If the study is not published yet, please choose Not yet.")
        title_given = bool(one_line(answers.get(Q["paper_title"])))
        title = paper_checks(new_paper if new_paper else "", data.get("paperTitle", "") if title_given else "",
                             new_data, notes)
        if new_paper and DOI.fullmatch(new_paper) and not title_given and title and title != data.get("paperTitle"):
            data["paperTitle"] = title
            changes.append(f"Paper title: {title}")
    else:
        if new_paper or new_data:
            notes.append("The study is not published yet, so the links under Paper and Data were not saved: "
                         "links are only shown once a study is published.")
        taken_off = [FIELD_NAMES[f] for f in ("paper", "dataUrl") if data.pop(f, None)]
        if taken_off:
            notes.append("The study is now listed as not yet published, so its links ("
                         + " and ".join(taken_off) + ") were taken off the page.")

    labels, texts = data.setdefault("labels", {}), data.setdefault("descriptions", {})
    touched = []
    for item in chosen(answers.get(Q["add_labels"])):
        cat, option = label_choice(options, item)
        if option in labels.get(cat["key"], []):
            notes.append(f"{item} was one of the study's labels already.")
            continue
        labels.setdefault(cat["key"], []).append(option)
        changes.append(f"Label added: {cat['label']}: {option}")
        touched.append(cat)
    for item in chosen(answers.get(Q["remove_labels"])):
        cat, option = label_choice(options, item)
        if option not in labels.get(cat["key"], []):
            notes.append(f"{item} was not one of the study's labels.")
            continue
        labels[cat["key"]].remove(option)
        if not labels[cat["key"]]:
            del labels[cat["key"]]
        changes.append(f"Label removed: {cat['label']}: {option}")
        touched.append(cat)
    for cat in {c["key"]: c for c in touched}.values():
        if cat["key"] in texts:
            notes.append(f'The study\'s own description of {cat["label"]} ("{texts.pop(cat["key"])}") was removed, '
                         "as its labels changed; Details now shows the labels instead.")

    if not changes and not other:
        if filled:
            return "done", "", ["Nothing needed changing: the study already has these details."] + notes
        raise Missing("Please fill in or tick at least one change.")
    if changes:
        order = [c["key"] for c in options["categories"]]
        path.write_text(dump_json(canonical_study(data, order)), encoding="utf-8")
        verified(root)
    reply = ([f"Changed on PredictIndex: {data['name']}"] + [f"- {c}" for c in changes] + [online(data["name"])]
             if changes else []) + notes
    summary = f"change {data['name']}" if changes else ""
    if other:
        reply.append("The other changes are not automatic. " + passed_on())
        return ("partial" if changes else "waiting"), summary, reply
    return "done", summary, reply


def change_options(answers, root, options, studies):
    cat = category_by_label(options, answers.get(Q["category"]))
    if not cat:
        raise Missing("Please choose the category again in a new form; the list is updated after every change.")
    action = one_line(answers.get(Q["action"])).lower()
    current, new = one_line(answers.get(Q["current"])), one_line(answers.get(Q["new"]))

    def the_new_option():
        if not new:
            raise Missing(f"Please write the new option under {Q['new']}.")
        if "," in new:
            raise Missing("An option cannot contain a comma, since GitHub separates the options chosen in a "
                          "form with commas. Please write it without one, for example e.g. instead of e.g.,")
        if "@" in new:
            raise Missing("An option may not contain the character @.")
        return new

    def the_current_option():
        if not current:
            raise Missing(f"Please write the option as it is now under {Q['current']}.")
        found = option_in(cat, current)
        if not found:
            raise Missing(f'"{current}" is not an option of {cat["label"]}. Its options are: '
                          + ", ".join(cat["options"]) + ".")
        return found

    if action.startswith("add"):
        option = the_new_option()
        if option_in(cat, option):
            raise Missing(f'"{option_in(cat, option)}" is an option of {cat["label"]} already.')
        parent = parent_of(option)
        family = [o for o in cat["options"] if parent and (o == parent or parent_of(o) == parent)]
        add_option(options, cat["key"], option, after=family[-1] if family else None)
        touched, said = [], f'{cat["label"]}: the option "{option}" was added.'
        summary = f'options: add "{option}" to {cat["label"]}'
    elif action.startswith("rename"):
        old, option = the_current_option(), the_new_option()
        if option == old:
            raise Missing("The new option is written exactly like the old one.")
        existing = option_in(cat, option)
        target = existing if existing and existing != old else option
        touched = rename_option(options, studies, cat["key"], old, target)
        said = (f'{cat["label"]}: "{old}" and "{target}" are now one option, "{target}".' if target == existing and existing != old
                else f'{cat["label"]}: the option "{old}" is now called "{target}".')
        summary = f'options: rename "{old}" to "{target}" in {cat["label"]}'
    elif action.startswith("remove"):
        old = the_current_option()
        if len(cat["options"]) == 1:
            raise Missing(f'"{old}" is the only option of {cat["label"]}, and a category needs at least one. '
                          "To remove the whole category, please use the form Anything else.")
        touched = remove_option(options, studies, cat["key"], old)
        said = f'{cat["label"]}: the option "{old}" was removed.'
        summary = f'options: remove "{old}" from {cat["label"]}'
    else:
        raise Missing("Please choose what should change: Add an option, Rename an option or Remove an option.")

    save(root, options, studies, ids=set(touched))
    verified(root)
    names = sorted(d["name"] for s, d in studies if s in touched)
    reply = [said]
    if names:
        reply.append(("This study has been changed with it: " if len(names) == 1 else
                      f"These {len(names)} studies have been changed with it: ") + "; ".join(names) + ".")
    reply.append("PredictIndex's filters and the forms of this repository follow in about a minute "
                 f"({site()}); the Google Form takes over the new options during the night.")
    return "done", summary, reply


def handle(issue, root, repo, env=None, permission=None):
    """Carries out one form. Returns (result, summary, reply lines)."""
    env = os.environ if env is None else env
    permission = permission or (lambda login: may_publish(login, repo))
    labels = {label["name"] for label in issue.get("labels", [])}
    kind = next((label for label in sorted(labels) if label.startswith("form: ")), None)
    action = env.get("EVENT_ACTION", "opened")
    if issue.get("state") != "open" or not kind or (action == "labeled" and env.get("EVENT_LABEL") != "approved"):
        return "skip", "", []
    answers = fields(issue.get("body"))
    email = next((m.group(0) for v in answers.values() for m in [EMAIL.search(v)] if m), None)
    email_reply = ("This form contains an e-mail address. Everything written in an issue is public, so please "
                   "remove it: click the three dots at the top right of your form text on this page, choose "
                   "Edit, delete the address and click Update comment. GitHub keeps the earlier version in the "
                   f"edit history; {the_maintainers()} can delete it there.")
    if kind == "form: other":
        if action != "opened":
            return "skip", "", []
        return "waiting", "", [passed_on()] + ([email_reply] if email else [])
    author = (issue.get("user") or {}).get("login", "")
    allowed = ((permission(author) and "test-as-member" not in labels)
               or ("approved" in labels and (action != "labeled" or permission(env.get("EVENT_SENDER", "")))))
    if not allowed:
        return ("waiting", "", [awaiting_approval()]) if action == "opened" else ("skip", "", [])
    if email:
        return "needs-info", "", ["Nothing has been changed yet. " + email_reply]
    options, studies = verified(root)
    try:
        if kind == "form: add":
            return add_study(answers, root, options, studies)
        if kind == "form: change":
            return change_study(answers, root, options, studies)
        if kind == "form: options":
            return change_options(answers, root, options, studies)
    except Missing as e:
        return "needs-info", "", ["Nothing has been changed yet. " + str(e), edit_hint(repo)]
    return "skip", "", []


def run_form(number, root, issue_file=None):
    repo = os.environ.get("GITHUB_REPOSITORY", REPO)
    issue = json.loads(Path(issue_file).read_text(encoding="utf-8") if issue_file
                       else gh("api", f"repos/{repo}/issues/{number}"))
    labels = {label["name"] for label in issue.get("labels", [])}
    if {"test", "test-crash"} <= labels:
        raise RuntimeError("Simulated failure, to test the reply that something went wrong")
    try:
        result, summary, reply = handle(issue, root, repo)
    except Exception:  # anything unforeseen: said in the issue, the details in the log
        import traceback
        traceback.print_exc()
        result, summary, reply = "error", "", [technical_problem()]
    print(f"result: {result}\nsummary: {summary}\n" + "\n".join(reply))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            out.write(f"result={result}\nsummary={one_line(summary)[:120]}\n")
    if os.environ.get("REPLY_FILE"):
        Path(os.environ["REPLY_FILE"]).write_text("\n\n".join(reply) + "\n", encoding="utf-8")
    return 0


# ------------------------------------------------- the generated form parts
#
# In a template, a line "# generated: <name>" starts a part that `sync`
# writes from the data, and "# end of generated: <name>" ends it; everything
# else in the templates is written by hand.

GENERATED = re.compile(r"^(\s*)# generated: ([\w-]+)")


def quoted(text):
    return json.dumps(text, ensure_ascii=False)  # a JSON string is a YAML string too


def generated_parts(options, studies):
    cats = options["categories"]
    checkboxes = []
    for c in cats:
        checkboxes += ["- type: checkboxes", f"  id: label_{c['key']}", "  attributes:",
                       f"    label: {quoted(c['label'])}",
                       f"    description: {quoted((c['help'] + ' ' if c.get('help') else '') + MULTIPLE)}",
                       "    options:"] + [f"      - label: {quoted(o)}" for o in c["options"]]
    names = [s["name"] for s in page_order([d for _, d in studies])] or ["(no studies yet)"]
    return {
        "label-checkboxes": checkboxes,
        "studies": [f"- {quoted(n)}" for n in names],
        "labels": [f"- {quoted(c['label'] + ': ' + o)}" for c in cats for o in c["options"]],
        "categories": [f"- {quoted(c['label'])}" for c in cats],
    }


def sync(root):
    """Writes the generated parts of the templates; returns the files changed."""
    root = Path(root)
    options, studies = verified(root)
    parts = generated_parts(options, studies)
    changed = []
    for template in sorted((root / TEMPLATES).glob("*.yml")):
        lines, out, i = template.read_text(encoding="utf-8").split("\n"), [], 0
        while i < len(lines):
            out.append(lines[i])
            marker = GENERATED.match(lines[i])
            i += 1
            if not marker or marker.group(2) not in parts:
                continue
            indent, name = marker.groups()
            end = next((j for j in range(i, len(lines)) if lines[j].strip() == f"# end of generated: {name}"), None)
            if end is None:
                raise ValueError(f'{template.name}: "# generated: {name}" has no line "# end of generated: {name}".')
            out += [indent + line for line in parts[name]] + [lines[end]]
            i = end + 1
        text = "\n".join(out)
        if text != template.read_text(encoding="utf-8"):
            template.write_text(text, encoding="utf-8")
            changed.append(template.name)
    return changed


# --------------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("build", "check the data and write studies.js"), ("check", "only check the data"),
                       ("form", "carry out the form of an issue"), ("sync", "write the generated parts of the forms")):
        p = sub.add_parser(name, help=text)
        p.add_argument("--root", type=Path, default=ROOT, help="the repository (default: this script's)")
        if name == "build":
            p.add_argument("--out", type=Path, help=f"where to write the page data (default: <root>/{PAGE_DATA})")
        if name == "form":
            p.add_argument("number", help="the issue's number")
            p.add_argument("--issue-file", help="read the issue from this JSON file instead of from GitHub")
    args = parser.parse_args()

    if args.command == "form":
        return run_form(args.number, args.root, args.issue_file)
    if args.command == "sync":
        changed = sync(args.root)
        print("Brought up to date: " + ", ".join(changed) if changed else "The forms are up to date.")
        return 0
    if args.command == "check":
        problems, _, studies = load(args.root)
    else:
        problems = build(args.root, args.out)
        studies = load(args.root)[2] if not problems else []
    if problems:
        print("The data has problems, so nothing was written:" if args.command == "build"
              else "The data has problems:")
        for p in problems:
            print("- " + p)
        return 1
    published = sum(1 for _, d in studies if d.get("published") is True)
    done = f"wrote {args.out or args.root / PAGE_DATA}" if args.command == "build" else "all checks passed"
    print(f"{len(studies)} studies, {published} published: {done}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
