"""Tests of the forms (.github/scripts/predictindex.py: handle, sync, run_form).

    python3 -m unittest discover -s tests

Made-up issues are carried out on made-up data in a temporary folder that holds
copies of the repository's form templates. doi.org and the data links are not
asked: lookup_doi, link_status and today are replaced for the tests.
"""

import importlib.util
import json
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / ".github" / "scripts" / "predictindex.py"
spec = importlib.util.spec_from_file_location("predictindex_forms", SCRIPT)
pi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pi)
Q = pi.Q

OPTIONS = {"categories": [
    {"key": "species", "label": "Species", "options": ["Human", "Mouse"]},
    {"key": "population", "label": "Population",
     "options": ["Healthy", "Clinical: autism", "Clinical: schizophrenia", "Clinical: other"]},
    {"key": "paradigm", "label": "Task paradigm", "options": ["Oddball", "Rating", "Recognition"]},
    {"key": "technique", "label": "Recording technique", "options": ["EEG", "fMRI", "Pupillometry"]},
]}
PUBLISHED = {
    "name": "A published study", "paperTitle": "The paper's title", "authors": "Ann Author & Ben Author",
    "correspondingAuthor": "Ann Author", "published": True, "paper": "10.1234/abcd.5678",
    "dataUrl": "https://osf.io/abcde/", "participants": "30", "sessions": "1", "added": "2026-09-12",
    "labels": {"species": ["Human"], "paradigm": ["Rating"], "technique": ["EEG"]},
    "descriptions": {"paradigm": "rating statements on a scale"},
}
UNPUBLISHED = {
    "name": "An unpublished study", "authors": "Cara Author", "correspondingAuthor": "Cara Author",
    "published": False, "added": "2026-11-23", "labels": {"species": ["Human"], "paradigm": ["Rating"]},
}
DOIS = {"10.1234/abcd.5678": "The paper's title", "10.5555/new.paper": "A Registered <i>Title</i> &amp; More"}


def body(*answers):
    """An issue body as GitHub writes it for a form: ### question, then the answer.
    A list stands for a group of checkboxes, its items the ticked options."""
    parts = []
    for question, answer in answers:
        if isinstance(answer, list):
            text = "\n".join(f"- [X] {a}" for a in answer) + "\n- [ ] (an option not ticked)"
        else:
            text = answer or "_No response_"
        parts.append(f"### {question}\n\n{text}")
    return "\n\n".join(parts)


def issue(kind, *answers, labels=(), user="writer", state="open"):
    return {"number": 7, "state": state, "user": {"login": user}, "body": body(*answers),
            "labels": [{"name": f"form: {kind}"}] + [{"name": label} for label in labels]}


def add_form(**over):
    answers = {Q["name"]: "A new study", Q["paper_title"]: "", Q["authors"]: "Dan Author, Eve Author and Fay Author",
               Q["corresponding"]: "Dan Author", Q["published"]: "Yes", Q["paper"]: "10.5555/new.paper",
               Q["data"]: "https://osf.io/newdt/", Q["participants"]: "24", Q["sessions"]: "",
               "Species": ["Human"], "Recording technique": ["EEG", "Pupillometry"],
               Q["google"]: "", Q["notes"]: ""}
    answers.update(over)
    return [(q, a) for q, a in answers.items() if a is not None]


class Forms(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "studies").mkdir()
        shutil.copytree(REPO / ".github" / "ISSUE_TEMPLATE", self.root / ".github" / "ISSUE_TEMPLATE")
        self.write("options.json", OPTIONS)
        self.write("studies/published.json", PUBLISHED)
        self.write("studies/unpublished.json", UNPUBLISHED)
        self.patches = [mock.patch.object(pi, "lookup_doi", lambda doi: (True, DOIS[doi]) if doi in DOIS else
                                          (None, "") if doi == "10.4444/offline" else (False, "")),
                        mock.patch.object(pi, "link_status", lambda url: 403 if "private" in url else
                                          None if "offline" in url else 200),
                        mock.patch.object(pi, "today", lambda: "2026-11-24"),
                        mock.patch.dict(os.environ, {"MAINTAINER": "hannah kirsten", "RUN_URL": "", "SITE_URL": "",
                                                     "GITHUB_REPOSITORY": "predcommlab/network-datasets"})]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.root)

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def study(self, sid):
        path = self.root / "studies" / f"{sid}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def options(self):
        return json.loads((self.root / "options.json").read_text(encoding="utf-8"))

    def run_form(self, the_issue, action="opened", label="", sender="writer", writers=("writer",)):
        env = {"EVENT_ACTION": action, "EVENT_LABEL": label, "EVENT_SENDER": sender}
        result, summary, reply = pi.handle(the_issue, self.root, "predcommlab/network-datasets", env=env,
                                           permission=lambda login: login in writers)
        text = "\n\n".join(reply)
        if result in ("done", "partial"):
            self.assertEqual(pi.load(self.root)[0], [], "the data must pass the checks after a form")
        return result, summary, text

    def assertNothingChanged(self):
        self.assertEqual(self.study("published"), PUBLISHED)
        self.assertEqual(self.study("unpublished"), UNPUBLISHED)
        self.assertEqual(self.options(), OPTIONS)
        self.assertEqual(sorted(p.name for p in (self.root / "studies").iterdir()), ["published.json", "unpublished.json"])


class AddAStudy(Forms):
    def test_a_published_study(self):
        result, summary, text = self.run_form(issue("add", *add_form()))
        self.assertEqual(result, "done")
        self.assertEqual(summary, "add A new study")
        s = self.study("a-new-study")
        self.assertEqual(s, {
            "name": "A new study", "paperTitle": "A Registered Title & More",
            "authors": "Dan Author, Eve Author & Fay Author", "correspondingAuthor": "Dan Author",
            "published": True, "paper": "10.5555/new.paper", "dataUrl": "https://osf.io/newdt/",
            "participants": "24", "added": "2026-11-24",
            "labels": {"species": ["Human"], "technique": ["EEG", "Pupillometry"]}})
        self.assertIn("Added to PredictIndex: A new study.", text)
        self.assertIn("https://predcommlab.github.io/network-datasets/?q=A+new+study", text)
        self.assertIn("The paper's title was taken from doi.org: A Registered Title & More", text)

    def test_a_title_given_is_kept(self):
        self.run_form(issue("add", *add_form(**{Q["paper_title"]: "My own title"})))
        self.assertEqual(self.study("a-new-study")["paperTitle"], "My own title")

    def test_an_unpublished_study_keeps_no_links(self):
        result, _, text = self.run_form(issue("add", *add_form(**{Q["published"]: "Not yet"})))
        self.assertEqual(result, "done")
        s = self.study("a-new-study")
        self.assertFalse(s["published"])
        self.assertNotIn("paper", s)
        self.assertNotIn("dataUrl", s)
        self.assertNotIn("paperTitle", s)
        self.assertIn("not published yet, so the links under Paper and Data were not saved", text)

    def test_a_published_study_needs_its_paper(self):
        result, _, text = self.run_form(issue("add", *add_form(**{Q["paper"]: ""})))
        self.assertEqual(result, "needs-info")
        self.assertIn("A published study needs its paper", text)
        self.assertIn("Update comment", text)
        self.assertNothingChanged()

    def test_a_name_that_is_taken(self):
        result, _, text = self.run_form(issue("add", *add_form(**{Q["name"]: "a  PUBLISHED study"})))
        self.assertEqual(result, "needs-info")
        self.assertIn('There is already a study called "a PUBLISHED study"', text)
        self.assertNothingChanged()

    def test_required_answers(self):
        result, _, text = self.run_form(issue("add", *add_form(**{Q["authors"]: "", Q["corresponding"]: ""})))
        self.assertEqual(result, "needs-info")
        self.assertIn("Please fill in: Authors, Corresponding author.", text)

    def test_a_doi_that_does_not_exist(self):
        result, _, text = self.run_form(issue("add", *add_form(**{Q["paper"]: "10.9999/nothing"})))
        self.assertEqual(result, "needs-info")
        self.assertIn("could not be found at doi.org", text)
        self.assertNothingChanged()

    def test_doi_org_not_answering(self):
        result, _, text = self.run_form(issue("add", *add_form(**{Q["paper"]: "10.4444/offline"})))
        self.assertEqual(result, "done")
        self.assertNotIn("paperTitle", self.study("a-new-study"))
        self.assertIn("could not be checked just now", text)

    def test_a_doi_written_as_a_link(self):
        for written in ("https://doi.org/10.5555/new.paper", "doi:10.5555/new.paper", "https://dx.doi.org/10.5555/new.paper"):
            with self.subTest(written=written):
                self.run_form(issue("add", *add_form(**{Q["name"]: written, Q["paper"]: written})))
                sid = pi.new_id(written, set())
                self.assertEqual(self.study(sid)["paper"], "10.5555/new.paper")

    def test_a_paper_that_is_neither_doi_nor_link(self):
        result, _, text = self.run_form(issue("add", *add_form(**{Q["paper"]: "Journal of Things 2024"})))
        self.assertEqual(result, "needs-info")
        self.assertIn("neither a DOI", text)

    def test_a_data_link_that_does_not_open(self):
        result, _, text = self.run_form(issue("add", *add_form(**{Q["data"]: "https://osf.io/private/"})))
        self.assertEqual(result, "done")
        self.assertEqual(self.study("a-new-study")["dataUrl"], "https://osf.io/private/")
        self.assertIn("answers with an error (status 403)", text)

    def test_a_data_field_that_is_not_a_link(self):
        result, _, text = self.run_form(issue("add", *add_form(**{Q["data"]: "on request"})))
        self.assertEqual(result, "needs-info")
        self.assertIn("is not a link", text)

    def test_answers_from_the_google_form(self):
        lines = "\n".join(["Species: human", "Population: Clinical: autism", "Recording technique: EEG",
                           "Recording technique: tactile vibration", "Signal level: BOLD", "nonsense"])
        result, _, text = self.run_form(issue("add", *add_form(**{Q["google"]: lines, "Recording technique": ["fMRI"]})))
        self.assertEqual(result, "done")
        s = self.study("a-new-study")
        self.assertEqual(s["labels"], {"species": ["Human"], "population": ["Clinical: autism"], "technique": ["fMRI", "EEG"]})
        self.assertEqual(s["descriptions"], {"technique": "EEG, tactile vibration"})
        self.assertIn('"tactile vibration" is not an option of Recording technique', text)
        self.assertIn('The line "Signal level: BOLD"', text)
        self.assertIn('The line "nonsense"', text)

    def test_an_e_mail_address_anywhere(self):
        result, _, text = self.run_form(issue("add", *add_form(**{Q["notes"]: "Questions to dan@example.org please"})))
        self.assertEqual(result, "needs-info")
        self.assertIn("This form contains an e-mail address", text)
        self.assertIn("@hannah, @kirsten", text)
        self.assertNothingChanged()

    def test_an_at_sign_in_a_name(self):
        result, _, text = self.run_form(issue("add", *add_form(**{Q["corresponding"]: "@dan"})))
        self.assertEqual(result, "needs-info")
        self.assertIn("Corresponding author may not contain the character @", text)

    def test_an_option_that_is_no_longer_there(self):
        result, _, text = self.run_form(issue("add", *add_form(**{"Task paradigm": ["Prediction"]})))
        self.assertEqual(result, "needs-info")
        self.assertIn('"Prediction" is no longer an option of Task paradigm', text)

    def test_file_names(self):
        self.assertEqual(pi.new_id("Pupil, cue uncertainty & outcome surprise", set()), "pupil-cue-uncertainty-outcome-surprise")
        self.assertEqual(pi.new_id("Über Ähnlichkeit (EEG)", set()), "uber-ahnlichkeit-eeg")
        self.assertEqual(pi.new_id("A study", {"a-study", "a-study-2"}), "a-study-3")
        self.assertEqual(pi.new_id("!!!", set()), "study")
        long = pi.new_id("Sensory sharpening and semantic prediction errors unify competing models of predictive processing", set())
        self.assertLessEqual(len(long), 60)
        self.assertFalse(long.endswith("-"))

    def test_authors_as_the_page_writes_them(self):
        self.assertEqual(pi.house_authors("Ann Author, Ben Author and Cara Author"), "Ann Author, Ben Author & Cara Author")
        self.assertEqual(pi.house_authors("Ann Author; Ben Author"), "Ann Author & Ben Author")
        self.assertEqual(pi.house_authors("Ann Author"), "Ann Author")
        self.assertEqual(pi.house_authors("Becker, J., Korn, C. W. & Blank, H."), "Becker, J., Korn, C. W. & Blank, H.")


class ChangeAStudy(Forms):
    def change(self, study="A published study", **answers):
        pairs = [(Q["study"], study)] + [(Q[k] if k in Q else k, v) for k, v in answers.items()]
        return self.run_form(issue("change", *pairs))

    def test_fields_filled_in_change(self):
        result, summary, text = self.change(name="A renamed study", participants="32", authors="Ann Author, Ben Author, Cara Author")
        self.assertEqual((result, summary), ("done", "change A renamed study"))
        s = self.study("published")
        self.assertEqual((s["name"], s["participants"], s["authors"]), ("A renamed study", "32", "Ann Author, Ben Author & Cara Author"))
        self.assertIn("- Study name: A renamed study", text)
        self.assertIn("- Number of participants: 32", text)
        self.assertEqual(s["paper"], PUBLISHED["paper"])  # the rest stays

    def test_a_name_another_study_has(self):
        result, _, text = self.change(name="An unpublished study")
        self.assertEqual(result, "needs-info")
        self.assertNothingChanged()

    def test_a_dash_empties_a_field(self):
        result, _, text = self.change(sessions="-")
        self.assertEqual(result, "done")
        self.assertNotIn("sessions", self.study("published"))
        self.assertIn("- Number of sessions: removed", text)
        result, _, text = self.change(authors="-")
        self.assertEqual(result, "needs-info")
        self.assertIn("Authors cannot be emptied", text)

    def test_publishing_a_study(self):
        result, _, text = self.change("An unpublished study", published="Yes", paper="https://doi.org/10.5555/new.paper",
                                      data="https://osf.io/newdt/")
        self.assertEqual(result, "done")
        s = self.study("unpublished")
        self.assertEqual((s["published"], s["paper"], s["dataUrl"], s["paperTitle"]),
                         (True, "10.5555/new.paper", "https://osf.io/newdt/", "A Registered Title & More"))
        self.assertIn("- Published: yes", text)

    def test_publishing_needs_the_paper(self):
        result, _, text = self.change("An unpublished study", published="Yes")
        self.assertEqual(result, "needs-info")
        self.assertIn("A published study needs its paper", text)
        self.assertNothingChanged()

    def test_unpublishing_takes_the_links_off(self):
        result, _, text = self.change(published="Not yet")
        self.assertEqual(result, "done")
        s = self.study("published")
        self.assertFalse(s["published"])
        self.assertNotIn("paper", s)
        self.assertNotIn("dataUrl", s)
        self.assertIn("were taken off the page", text)

    def test_links_for_an_unpublished_study_are_not_saved(self):
        result, _, text = self.change("An unpublished study", data="https://osf.io/newdt/", participants="12")
        self.assertEqual(result, "done")
        self.assertNotIn("dataUrl", self.study("unpublished"))
        self.assertIn("were not saved", text)

    def test_labels_added_and_removed(self):
        result, _, text = self.change(add_labels="Population: Clinical: autism, Task paradigm: Oddball, Species: Human",
                                      remove_labels="Recording technique: EEG, Task paradigm: Recognition")
        self.assertEqual(result, "done")
        s = self.study("published")
        self.assertEqual(s["labels"], {"species": ["Human"], "population": ["Clinical: autism"], "paradigm": ["Rating", "Oddball"]})
        self.assertNotIn("descriptions", s)  # its only description was of Task paradigm, whose labels changed
        self.assertIn("- Label added: Population: Clinical: autism", text)
        self.assertIn("- Label removed: Recording technique: EEG", text)
        self.assertIn("Species: Human was one of the study's labels already.", text)
        self.assertIn("Task paradigm: Recognition was not one of the study's labels.", text)
        self.assertIn('own description of Task paradigm ("rating statements on a scale") was removed', text)

    def test_a_label_that_is_no_longer_there(self):
        result, _, text = self.change(add_labels="Task paradigm: Prediction")
        self.assertEqual(result, "needs-info")
        self.assertIn("is no longer one of the labels", text)

    def test_removing_a_study(self):
        result, summary, text = self.change(remove=["Remove this study from PredictIndex."], participants="99")
        self.assertEqual((result, summary), ("done", "remove A published study"))
        self.assertIsNone(self.study("published"))
        self.assertIn("Removed from PredictIndex: A published study.", text)
        self.assertIn("were not needed", text)

    def test_a_study_that_is_not_there(self):
        result, _, text = self.change("A study renamed meanwhile", participants="5")
        self.assertEqual(result, "needs-info")
        self.assertIn("There is no study called", text)

    def test_nothing_filled_in(self):
        result, _, text = self.change()
        self.assertEqual(result, "needs-info")
        self.assertIn("at least one change", text)

    def test_nothing_needed_changing(self):
        result, summary, text = self.change(participants="30")
        self.assertEqual((result, summary), ("done", ""))
        self.assertIn("Nothing needed changing", text)
        self.assertNothingChanged()

    def test_other_changes_go_to_a_person(self):
        result, _, text = self.change(other="Please also mention the second dataset.")
        self.assertEqual(result, "waiting")
        self.assertIn("This has been passed on to the people who look after PredictIndex (@hannah, @kirsten)", text)
        result, _, text = self.change(participants="31", other="And the second dataset.")
        self.assertEqual(result, "partial")
        self.assertIn("- Number of participants: 31", text)


class ChangeTheOptions(Forms):
    def options_form(self, category, action, current="", new=""):
        return self.run_form(issue("options", (Q["category"], category), (Q["action"], action),
                                   (Q["current"], current), (Q["new"], new)))

    def test_adding_an_option(self):
        result, summary, text = self.options_form("Recording technique", "Add an option", new="MEG")
        self.assertEqual((result, summary), ("done", 'options: add "MEG" to Recording technique'))
        self.assertEqual(self.options()["categories"][3]["options"], ["EEG", "fMRI", "Pupillometry", "MEG"])
        self.assertIn('Recording technique: the option "MEG" was added.', text)
        self.assertIn("the Google Form takes over the new options during the night", text)

    def test_a_sub_option_joins_its_family(self):
        self.options_form("Population", "Add an option", new="Clinical: dyslexia")
        self.assertEqual(self.options()["categories"][1]["options"],
                         ["Healthy", "Clinical: autism", "Clinical: schizophrenia", "Clinical: other", "Clinical: dyslexia"])

    def test_adding_an_option_that_is_there(self):
        result, _, text = self.options_form("Recording technique", "Add an option", new="eeg")
        self.assertEqual(result, "needs-info")
        self.assertIn('"EEG" is an option of Recording technique already', text)

    def test_an_option_with_a_comma(self):
        result, _, text = self.options_form("Recording technique", "Add an option", new="Ambiguous (e.g., morphed)")
        self.assertEqual(result, "needs-info")
        self.assertIn("cannot contain a comma", text)
        self.assertNothingChanged()

    def test_renaming_an_option(self):
        result, _, text = self.options_form("Task paradigm", "Rename an option", current="rating", new="Rating task")
        self.assertEqual(result, "done")
        self.assertEqual(self.options()["categories"][2]["options"], ["Oddball", "Rating task", "Recognition"])
        self.assertEqual(self.study("published")["labels"]["paradigm"], ["Rating task"])
        self.assertEqual(self.study("unpublished")["labels"]["paradigm"], ["Rating task"])
        self.assertIn('the option "Rating" is now called "Rating task"', text)
        self.assertIn("These 2 studies have been changed with it: A published study; An unpublished study.", text)

    def test_renaming_onto_another_option_merges_them(self):
        result, _, text = self.options_form("Task paradigm", "Rename an option", current="Rating", new="oddball")
        self.assertEqual(result, "done")
        self.assertEqual(self.options()["categories"][2]["options"], ["Oddball", "Recognition"])
        self.assertEqual(self.study("published")["labels"]["paradigm"], ["Oddball"])
        self.assertIn('are now one option, "Oddball"', text)

    def test_renaming_only_the_capitals(self):
        result, _, _ = self.options_form("Recording technique", "Rename an option", current="fMRI", new="FMRI")
        self.assertEqual(result, "done")
        self.assertEqual(self.options()["categories"][3]["options"], ["EEG", "FMRI", "Pupillometry"])

    def test_removing_an_option(self):
        result, _, text = self.options_form("Recording technique", "Remove an option", current="EEG")
        self.assertEqual(result, "done")
        self.assertEqual(self.options()["categories"][3]["options"], ["fMRI", "Pupillometry"])
        self.assertNotIn("technique", self.study("published")["labels"])
        self.assertIn("This study has been changed with it: A published study.", text)

    def test_the_last_option_stays(self):
        self.options_form("Recording technique", "Remove an option", current="fMRI")
        self.options_form("Recording technique", "Remove an option", current="Pupillometry")
        result, _, text = self.options_form("Recording technique", "Remove an option", current="EEG")
        self.assertEqual(result, "needs-info")
        self.assertIn("is the only option of Recording technique", text)

    def test_an_option_that_is_not_there(self):
        result, _, text = self.options_form("Recording technique", "Remove an option", current="MEG")
        self.assertEqual(result, "needs-info")
        self.assertIn("Its options are: EEG, fMRI, Pupillometry.", text)

    def test_no_action_chosen(self):
        result, _, _ = self.options_form("Recording technique", "", new="MEG")
        self.assertEqual(result, "needs-info")


class WhoMayChangeWhat(Forms):
    def test_a_member_s_form_waits_for_approval(self):
        result, _, text = self.run_form(issue("add", *add_form(), user="member"))
        self.assertEqual(result, "waiting")
        self.assertIn("adds the label approved", text)
        self.assertNothingChanged()

    def test_editing_a_waiting_form_does_not_reply_again(self):
        result, _, _ = self.run_form(issue("add", *add_form(), user="member"), action="edited", sender="member")
        self.assertEqual(result, "skip")

    def test_approved_by_someone_with_write_access(self):
        result, _, _ = self.run_form(issue("add", *add_form(), user="member", labels=["approved"]),
                                     action="labeled", label="approved", sender="writer")
        self.assertEqual(result, "done")
        self.assertIsNotNone(self.study("a-new-study"))

    def test_approved_by_someone_without_write_access(self):
        result, _, _ = self.run_form(issue("add", *add_form(), user="member", labels=["approved"]),
                                     action="labeled", label="approved", sender="member")
        self.assertEqual(result, "skip")
        self.assertNothingChanged()

    def test_an_approved_form_edited_later_is_read_again(self):
        result, _, _ = self.run_form(issue("add", *add_form(), user="member", labels=["approved"]),
                                     action="edited", sender="member")
        self.assertEqual(result, "done")

    def test_another_label(self):
        result, _, _ = self.run_form(issue("add", *add_form(), labels=["bug"]), action="labeled", label="bug")
        self.assertEqual(result, "skip")

    def test_test_as_member(self):
        result, _, _ = self.run_form(issue("add", *add_form(), labels=["test", "test-as-member"]))
        self.assertEqual(result, "waiting")

    def test_a_closed_issue_or_one_without_a_form(self):
        self.assertEqual(self.run_form(issue("add", *add_form(), state="closed"))[0], "skip")
        no_form = issue("add", *add_form())
        no_form["labels"] = [{"name": "bug"}]
        self.assertEqual(self.run_form(no_form)[0], "skip")

    def test_anything_else_goes_to_a_person_from_anyone(self):
        result, _, text = self.run_form(issue("other", ("What should change?", "Please add a menu item."), user="stranger"))
        self.assertEqual(result, "waiting")
        self.assertIn("passed on to the people who look after PredictIndex (@hannah, @kirsten)", text)
        self.assertEqual(self.run_form(issue("other", ("What should change?", "x")), action="edited")[0], "skip")


class RunningAForm(Forms):
    def run_file(self, the_issue, extra_env=None):
        path = self.root / "issue.json"
        path.write_text(json.dumps(the_issue), encoding="utf-8")
        out, reply = self.root / "output", self.root / "reply.md"
        env = {"GITHUB_OUTPUT": str(out), "REPLY_FILE": str(reply), "EVENT_ACTION": "opened",
               "GITHUB_REPOSITORY": "predcommlab/network-datasets", **(extra_env or {})}
        with mock.patch.dict(os.environ, env), mock.patch.object(pi, "may_publish", lambda login, repo: True), \
                mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            pi.run_form("7", self.root, str(path))
        return out.read_text(encoding="utf-8"), reply.read_text(encoding="utf-8")

    def test_the_outputs_for_the_workflow(self):
        out, reply = self.run_file(issue("add", *add_form(**{Q["name"]: "A new\nstudy"})))
        self.assertEqual(out, "result=done\nsummary=add A new study\n")
        self.assertIn("Added to PredictIndex: A new study.", reply)

    def test_an_unforeseen_error_is_said_in_the_issue(self):
        (self.root / "options.json").write_text("{", encoding="utf-8")  # the data is broken
        out, reply = self.run_file(issue("add", *add_form()), {"RUN_URL": "https://example.org/run/1"})
        self.assertEqual(out, "result=error\nsummary=\n")
        self.assertIn("because of a technical problem, so nothing has been changed", reply)
        self.assertIn("@hannah, @kirsten", reply)
        self.assertIn("Details: https://example.org/run/1", reply)

    def test_test_crash_fails_on_purpose(self):
        with self.assertRaises(RuntimeError):
            self.run_file(issue("add", *add_form(), labels=["test", "test-crash"]))


class GeneratedFormParts(Forms):
    def template(self, name):
        return (self.root / ".github" / "ISSUE_TEMPLATE" / name).read_text(encoding="utf-8")

    def test_sync_writes_the_data_into_the_forms(self):
        changed = pi.sync(self.root)
        self.assertEqual(changed, ["1-add-a-study.yml", "2-change-a-study.yml", "3-change-the-options.yml"])
        add, change, opts = (self.template(n) for n in ("1-add-a-study.yml", "2-change-a-study.yml", "3-change-the-options.yml"))
        self.assertIn('    id: label_population\n    attributes:\n      label: "Population"', add)
        self.assertIn('        - label: "Clinical: schizophrenia"', add)
        self.assertIn('        - "An unpublished study"\n        - "A published study"\n        # end of generated: studies', change)
        self.assertEqual(change.count('        - "Population: Clinical: autism"'), 2)
        self.assertIn('        - "Recording technique"\n        # end of generated: categories', opts)
        self.assertEqual(pi.sync(self.root), [])  # a second run changes nothing

    def test_a_form_changes_the_lists_after_the_next_sync(self):
        pi.sync(self.root)
        self.run_form(issue("options", (Q["category"], "Recording technique"), (Q["action"], "Add an option"),
                            (Q["current"], ""), (Q["new"], "MEG")))
        self.assertEqual(pi.sync(self.root), ["1-add-a-study.yml", "2-change-a-study.yml"])
        self.assertIn('"Recording technique: MEG"', self.template("2-change-a-study.yml"))

    def test_a_part_without_its_end(self):
        path = self.root / ".github" / "ISSUE_TEMPLATE" / "3-change-the-options.yml"
        path.write_text(path.read_text(encoding="utf-8").replace("# end of generated: categories", ""), encoding="utf-8")
        with self.assertRaises(ValueError):
            pi.sync(self.root)


class FormsAndScriptAgree(unittest.TestCase):
    """The questions the script reads are the questions of the repository's templates."""

    def labels(self, name):
        text = (REPO / ".github" / "ISSUE_TEMPLATE" / name).read_text(encoding="utf-8")
        return set(re.findall(r'^\s+label: "?(.+?)"?\s*$', text, re.M)), text

    def test_add_a_study(self):
        labels, text = self.labels("1-add-a-study.yml")
        for k in ("name", "paper_title", "authors", "corresponding", "published", "paper", "data",
                  "participants", "sessions", "google", "notes"):
            self.assertIn(Q[k], labels)
        self.assertIn('labels: ["form: add"]', text)

    def test_change_a_study(self):
        labels, text = self.labels("2-change-a-study.yml")
        for k in ("study", "remove", "name", "paper_title", "authors", "corresponding", "published", "paper",
                  "data", "participants", "sessions", "acquisition", "bids", "add_labels", "remove_labels", "other"):
            self.assertIn(Q[k], labels)
        self.assertIn('labels: ["form: change"]', text)

    def test_change_the_options(self):
        labels, text = self.labels("3-change-the-options.yml")
        for k in ("category", "action", "current", "new"):
            self.assertIn(Q[k], labels)
        self.assertIn('labels: ["form: options"]', text)

    def test_anything_else(self):
        labels, text = self.labels("4-anything-else.yml")
        self.assertIn("What should change?", labels)
        self.assertIn('labels: ["form: other"]', text)

    # Whether the repository's data passes the checks and whether the generated
    # parts of its forms are up to date is not tested here: the Deploy workflow
    # checks the data in a step of its own, with a plain message, and brings the
    # forms up to date itself (a study renamed in GitHub's editor, 2026-11-24).


if __name__ == "__main__":
    unittest.main()
