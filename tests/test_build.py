"""Tests of the checks and of studies.js (.github/scripts/predictindex.py).

    python3 -m unittest discover -s tests

Every rule is tried on made-up data in a temporary folder, so the tests do not
depend on which studies the repository holds. Whether the repository's own data
passes is checked by `predictindex.py check`, a step of its own in the Deploy
workflow.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / ".github" / "scripts" / "predictindex.py"
spec = importlib.util.spec_from_file_location("predictindex", SCRIPT)
pi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pi)

OPTIONS = {"categories": [
    {"key": "species", "label": "Species", "options": ["Human", "Mouse"]},
    {"key": "paradigm", "label": "Task paradigm", "options": ["Oddball", "Rating"]},
    {"key": "technique", "label": "Recording technique", "options": ["EEG", "fMRI"]},
    {"key": "predictability", "label": "Predictability", "filter": False, "options": ["Random"]},
]}
PUBLISHED = {
    "name": "A published study",
    "paperTitle": "The paper's title",
    "authors": "Ann Author & Ben Author",
    "correspondingAuthor": "Ann Author",
    "published": True,
    "paper": "10.1234/abcd.5678",
    "dataUrl": "https://osf.io/abcde/",
    "participants": "30",
    "added": "2026-09-12",
    "labels": {"species": ["Human"], "technique": ["EEG", "fMRI"]},
    "additionalInfo": "Task: listening to tones",
}
UNPUBLISHED = {
    "name": "An unpublished study",
    "authors": "Cara Author",
    "correspondingAuthor": "Cara Author",
    "published": False,
    "added": "2026-11-23",
    "labels": {"species": ["Mouse"]},
}


class Data(unittest.TestCase):
    """A temporary repository with the made-up options and two studies."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "studies").mkdir()
        self.write("options.json", OPTIONS)
        self.write("studies/published.json", PUBLISHED)
        self.write("studies/unpublished.json", UNPUBLISHED)

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, name, value):
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        (self.root / name).write_text(text, encoding="utf-8")

    def change(self, file, **fields):
        """Rewrites a study file with some fields changed (None removes one)."""
        path = self.root / "studies" / file
        data = json.loads(path.read_text(encoding="utf-8"))
        for k, v in fields.items():
            if v is None:
                data.pop(k, None)
            else:
                data[k] = v
        self.write("studies/" + file, data)

    def problems(self):
        return pi.load(self.root)[0]

    def assertProblem(self, *words):
        """Exactly one problem is found, and it contains all the words."""
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        for w in words:
            self.assertIn(w, found[0])


class Checks(Data):
    def test_the_made_up_data_passes(self):
        self.assertEqual(self.problems(), [])

    def test_a_label_that_is_not_an_option(self):
        self.change("published.json", labels={"species": ["Monkey"]})
        self.assertProblem("studies/published.json", '"Monkey" is not one of the options of Species',
                           "Human, Mouse")

    def test_a_label_of_an_unknown_category(self):
        self.change("published.json", labels={"colour": ["Red"]})
        self.assertProblem('"colour" is not a category')

    def test_a_label_listed_twice(self):
        self.change("published.json", labels={"technique": ["EEG", "EEG"]})
        self.assertProblem("listed twice")

    def test_labels_have_to_be_a_list(self):
        self.change("published.json", labels={"species": "Human"})
        self.assertProblem("has to be a list of options")

    def test_an_unpublished_study_with_a_data_link(self):
        self.change("unpublished.json", dataUrl="https://osf.io/abcde/")
        self.assertProblem("studies/unpublished.json", "not published")

    def test_an_unpublished_study_with_a_paper(self):
        self.change("unpublished.json", paper="10.1234/abcd")
        self.assertProblem("not published")

    def test_a_data_link_that_is_not_a_web_address(self):
        for bad in ("osf.io/abcde", "not public", "javascript:alert(1)", "https://osf.io/a b"):
            with self.subTest(bad=bad):
                self.change("published.json", dataUrl=bad)
                self.assertProblem('"dataUrl" has to be a web address')

    def test_a_paper_is_a_doi_or_a_link(self):
        for good in ("10.1037/xge0000498", "https://elifesciences.org/articles/103689",
                     "https://doi.org/10.1038/s41598-024-59302-1"):
            with self.subTest(good=good):
                self.change("published.json", paper=good)
                self.assertEqual(self.problems(), [])
        self.change("published.json", paper="doi 10.1037")
        self.assertProblem('"paper" has to be a DOI')

    def test_no_e_mail_address_anywhere(self):
        self.change("published.json", additionalInfo="ask ann@example.org")
        self.assertProblem('contains "@"')
        self.change("published.json", additionalInfo="tones", correspondingAuthor="ann@example.org")
        self.assertProblem('contains "@"')

    def test_required_fields(self):
        for field in ("name", "authors", "correspondingAuthor", "published", "added"):
            with self.subTest(field=field):
                self.write("studies/published.json", {k: v for k, v in PUBLISHED.items() if k != field})
                self.assertProblem(f'"{field}" is missing')

    def test_published_is_true_or_false(self):
        self.change("published.json", published="yes")
        self.assertProblem('"published" has to be true or false')

    def test_added_is_a_date(self):
        for bad in ("2026-13-01", "24.11.2026", "2026-11-31"):
            with self.subTest(bad=bad):
                self.change("published.json", added=bad)
                self.assertProblem('"added" has to be a date')

    def test_text_fields_are_text(self):
        self.change("published.json", participants=30)
        self.assertProblem('"participants" has to be a piece of text')

    def test_an_unknown_field(self):
        self.change("published.json", institution="RUB")
        self.assertProblem('unknown field "institution"')

    def test_two_studies_with_the_same_name(self):
        self.change("unpublished.json", name="a  PUBLISHED study")
        self.assertProblem("the same name", "studies/published.json", "studies/unpublished.json")

    def test_a_file_that_is_not_json(self):
        self.write("studies/broken.json", '{"name": "Broken",}')
        self.assertProblem("studies/broken.json", "not valid JSON", "line 1")

    def test_a_file_name_with_a_space(self):
        self.write("studies/semantic priors.json", dict(PUBLISHED, name="Another name"))
        self.assertProblem("studies/semantic priors.json", "small letters, digits and hyphens")

    def test_files_macos_leaves_behind_are_ignored(self):
        self.write("studies/.DS_Store", "\x00\x01")
        self.assertEqual(self.problems(), [])

    def test_the_former_descriptions_are_refused(self):
        # merged into the labels and Additional information on 2026-11-25
        self.change("published.json", descriptions={"paradigm": "listening to tones"})
        self.assertProblem('unknown field "descriptions"')

    def test_additional_information_is_a_piece_of_text(self):
        self.change("published.json", additionalInfo=["a list"])
        self.assertProblem('"additionalInfo" has to be a piece of text')


class OptionChecks(Data):
    def options(self, change):
        options = json.loads(json.dumps(OPTIONS))
        change(options["categories"])
        self.write("options.json", options)

    def test_an_option_with_a_comma(self):
        self.options(lambda cats: cats[1]["options"].append("Ambiguous (e.g., morphed)"))
        self.assertProblem("contains a comma")

    def test_an_option_listed_twice(self):
        self.options(lambda cats: cats[0]["options"].append("human"))
        self.assertProblem('"human" is listed twice')

    def test_a_key_used_twice(self):
        self.options(lambda cats: cats.append(dict(cats[0], label="Species again")))
        self.assertProblem('the key "species" is used twice')

    def test_a_key_the_page_uses_itself(self):
        self.options(lambda cats: cats.append({"key": "status", "label": "Status", "options": ["A"]}))
        self.assertProblem("used by the page itself")

    def test_a_category_without_options(self):
        self.options(lambda cats: cats[0].update(options=[]))
        self.assertProblem("at least one option")

    def test_an_unknown_entry(self):
        self.options(lambda cats: cats[0].update(colour="blue"))
        self.assertProblem('unknown entry "colour"')

    def test_filter_is_true_or_false(self):
        self.options(lambda cats: cats[3].update(filter="no"))
        self.assertProblem('"filter" has to be true or false')

    def test_options_json_that_is_not_json(self):
        self.write("options.json", "{")
        self.assertProblem("options.json", "not valid JSON")


class ChangingOptions(Data):
    """add_option, rename_option, remove_option: options.json and the studies together."""

    def loaded(self):
        problems, options, studies = pi.load(self.root)
        self.assertEqual(problems, [])
        return options, studies

    def test_add_an_option_after_another_or_at_the_end(self):
        options, _ = self.loaded()
        pi.add_option(options, "paradigm", "Detection", after="Oddball")
        pi.add_option(options, "paradigm", "Memory")
        self.assertEqual(pi.category(options, "paradigm")["options"], ["Oddball", "Detection", "Rating", "Memory"])

    def test_rename_an_option_everywhere(self):
        self.change("unpublished.json", labels={"technique": ["EEG"]})
        options, studies = self.loaded()
        touched = pi.rename_option(options, studies, "technique", "EEG", "Electroencephalography")
        pi.save(self.root, options, studies)
        options, studies = self.loaded()
        data = dict(studies)
        self.assertEqual(sorted(touched), ["published", "unpublished"])
        self.assertEqual(pi.category(options, "technique")["options"], ["Electroencephalography", "fMRI"])
        self.assertEqual(data["published"]["labels"]["technique"], ["Electroencephalography", "fMRI"])
        self.assertEqual(data["unpublished"]["labels"]["technique"], ["Electroencephalography"])

    def test_a_rename_onto_an_existing_option_merges_the_two(self):
        options, studies = self.loaded()
        pi.rename_option(options, studies, "technique", "EEG", "fMRI")
        self.assertEqual(pi.category(options, "technique")["options"], ["fMRI"])
        self.assertEqual(dict(studies)["published"]["labels"]["technique"], ["fMRI"])

    def test_remove_an_option_everywhere(self):
        self.change("published.json", labels={"species": ["Human"], "paradigm": ["Rating"]})
        options, studies = self.loaded()
        touched = pi.remove_option(options, studies, "paradigm", "Rating")
        pi.save(self.root, options, studies)
        options, studies = self.loaded()
        data = dict(studies)["published"]
        self.assertEqual(touched, ["published"])
        self.assertEqual(pi.category(options, "paradigm")["options"], ["Oddball"])
        self.assertNotIn("paradigm", data["labels"])           # no empty list left behind
        self.assertEqual(data["labels"]["species"], ["Human"])

    def test_a_category_name_with_a_comma_or_a_colon(self):
        for bad in ("Task, paradigm", "Task: paradigm"):
            with self.subTest(bad=bad):
                options = json.loads(json.dumps(OPTIONS))
                options["categories"][1]["label"] = bad
                self.assertTrue(any("contains a comma or a colon" in p for p in pi.check_options(options)))

    def test_saved_options_keep_the_order_of_their_entries(self):
        options, studies = self.loaded()
        options["categories"].append({"options": ["A"], "label": "New", "key": "newCategory"})
        pi.save(self.root, options, studies)
        text = (self.root / "options.json").read_text(encoding="utf-8")
        self.assertLess(text.index('"key": "newCategory"'), text.index('"label": "New"'))
        self.assertLess(text.index('"label": "New"'), text.index('"options": [\n        "A"'))


class PageData(Data):
    def build(self):
        problems = pi.build(self.root)
        self.assertEqual(problems, [])
        text = (self.root / "studies.js").read_text(encoding="utf-8")
        studies = json.loads(text.split("const STUDIES = ", 1)[1].rstrip().rstrip(";"))
        options = json.loads(text.split("const OPTIONS = ", 1)[1].split(";\n\nconst STUDIES", 1)[0])
        return text, options, studies

    def test_what_the_page_gets(self):
        _, options, studies = self.build()
        self.assertEqual(options, OPTIONS)
        s = next(s for s in studies if s["id"] == "published")
        self.assertEqual(s["paperLink"], "https://doi.org/10.1234/abcd.5678")
        self.assertEqual(s["paperDoi"], "10.1234/abcd.5678")
        self.assertNotIn("paper", s)
        self.assertNotIn("preprint", s)
        self.assertEqual(s["labels"], {"species": ["Human"], "technique": ["EEG", "fMRI"]})
        self.assertEqual(s["additionalInfo"], "Task: listening to tones")
        u = next(s for s in studies if s["id"] == "unpublished")
        self.assertNotIn("paperLink", u)
        self.assertNotIn("dataUrl", u)
        self.assertNotIn("additionalInfo", u)

    def test_a_paper_link_that_is_not_a_doi(self):
        self.change("published.json", paper="https://elifesciences.org/articles/103689")
        s = next(s for s in self.build()[2] if s["id"] == "published")
        self.assertEqual(s["paperLink"], "https://elifesciences.org/articles/103689")
        self.assertNotIn("paperDoi", s)

    def test_preprints_are_recognised(self):
        for paper in ("10.1101/2024.01.01.123456", "https://www.biorxiv.org/content/10.1101/2024.01.01.123456v1",
                      "https://doi.org/10.31234/osf.io/abcde", "https://osf.io/preprints/psyarxiv/abcde"):
            with self.subTest(paper=paper):
                self.assertTrue(pi.is_preprint(paper))
        for paper in ("10.1037/xge0000498", "https://elifesciences.org/articles/103689", "https://osf.io/abcde/"):
            with self.subTest(paper=paper):
                self.assertFalse(pi.is_preprint(paper))

    def test_newest_first_then_by_name(self):
        self.write("studies/b.json", dict(UNPUBLISHED, name="beta", added="2026-09-12"))
        self.write("studies/a.json", dict(UNPUBLISHED, name="Alpha", added="2026-09-12"))
        names = [s["name"] for s in self.build()[2]]
        self.assertEqual(names, ["An unpublished study", "A published study", "Alpha", "beta"])

    def test_the_build_writes_the_same_file_every_time(self):
        first = self.build()[0]
        self.assertEqual(self.build()[0], first)

    def test_nothing_is_written_when_there_is_a_problem(self):
        self.change("published.json", labels={"species": ["Monkey"]})
        self.assertTrue(pi.build(self.root))
        self.assertFalse((self.root / "studies.js").exists())

    def test_the_command_line_says_what_is_wrong(self):
        self.change("unpublished.json", dataUrl="https://osf.io/abcde/")
        run = subprocess.run([sys.executable, "-I", "-B", str(SCRIPT), "build", "--root", str(self.root)],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        self.assertIn("nothing was written", run.stdout)
        self.assertIn("studies/unpublished.json", run.stdout)
        self.assertFalse((self.root / "studies.js").exists())

    def test_a_file_written_by_the_script_reads_back_the_same(self):
        order = [c["key"] for c in OPTIONS["categories"]]
        messy = dict(PUBLISHED, name="  A   published study ", labels={"technique": ["EEG"], "species": ["Human"]},
                     sessions="", additionalInfo="  Task:  listening\n to   tones \n\n Sample: online ")
        once = pi.dump_json(pi.canonical_study(messy, order))
        again = pi.dump_json(pi.canonical_study(json.loads(once), order))
        self.assertEqual(once, again)
        data = json.loads(once)
        self.assertEqual(data["name"], "A published study")
        self.assertEqual(list(data["labels"]), ["species", "technique"])
        self.assertNotIn("sessions", data)
        self.assertEqual(data["additionalInfo"], "Task: listening\nto tones\nSample: online")  # its lines kept


if __name__ == "__main__":
    unittest.main()
