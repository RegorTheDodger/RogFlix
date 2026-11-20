"""The rules that have no network in them.

Everything here is a decision the site makes about somebody else's catalogue:
which films may show the fifth source, which einthusan index a title matches,
which language a film was made in, and how two devices' state merge. Each one
has already been wrong once, so each one is pinned down.

Run with:  python -m unittest discover -s tests
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import einthusan_source, language, players, sync


class Gate(unittest.TestCase):
    """The fifth source is for Indian films, and only for films."""

    def test_india_alone_counts(self):
        self.assertTrue(einthusan_source.is_indian("India"))
        self.assertTrue(einthusan_source.is_indian("India, United States"))
        self.assertTrue(einthusan_source.is_indian("united states; india"))

    def test_other_countries_do_not(self):
        for country in ("Pakistan", "Bangladesh", "Sri Lanka", "Nepal",
                        "United States", "", None):
            self.assertFalse(einthusan_source.is_indian(country), country)

    def test_offers(self):
        self.assertTrue(einthusan_source.offers("movie", "India"))
        self.assertFalse(einthusan_source.offers("series", "India"))
        self.assertFalse(einthusan_source.offers("movie", "Pakistan"))

    def test_source_is_offered_last(self):
        indian = [one["key"] for one in
                  players.sources("movie", "tt8178634", "", country="India")]
        self.assertEqual(indian[-1], "einthusan")

    def test_source_list_is_gated_by_country(self):
        elsewhere = [one["key"] for one in
                     players.sources("movie", "tt8178634", "",
                                     country="Pakistan")]
        self.assertNotIn("einthusan", elsewhere)
        show = [one["key"] for one in
                players.sources("series", "tt0903747", "", 1, 1, "India")]
        self.assertNotIn("einthusan", show)

    def test_flag_takes_the_button_off(self):
        players.OFFER_EINTHUSAN = False
        try:
            indian = [one["key"] for one in
                      players.sources("movie", "tt8178634", "",
                                      country="India")]
            self.assertNotIn("einthusan", indian)
        finally:
            players.OFFER_EINTHUSAN = True


class Matching(unittest.TestCase):
    """Title-and-year matching, which decides which film einthusan plays."""

    def test_first_word_pass(self):
        self.assertEqual(einthusan_source._first_word("Kalki 2898 AD"), "Kalki")
        self.assertEqual(einthusan_source._first_word("RRR"), "")

    def test_year_settles_a_remake(self):
        item = {"title": "Sholay", "year": "1975"}
        self.assertGreater(einthusan_source._score("Sholay", 1975, item), 0.9)
        self.assertEqual(einthusan_source._score("Sholay", 2007, item), 0.0)

    def test_one_year_of_slack(self):
        item = {"title": "Sholay", "year": "1975"}
        self.assertGreater(einthusan_source._score("Sholay", 1976, item), 0.8)


class Find(unittest.TestCase):
    """Every index holding the film is kept, not just the closest one."""

    PAGES = {
        ("RRR", "tamil"): [{"id": "6jRm", "title": "RRR", "year": "2022",
                            "lang": "Tamil"}],
        ("RRR", "telugu"): [{"id": "35hu", "title": "RRR", "year": "2022",
                             "lang": "Telugu"}],
        ("RRR", "hindi"): [{"id": "1D3Q", "title": "RRR", "year": "2022",
                            "lang": "Hindi"}],
        # einthusan shortens a title in some indexes, and that must not hide
        # the language the film was made in
        ("Baahubali 2: The Conclusion", "tamil"): [
            {"id": "6BU0", "title": "Baahubali 2: The Conclusion",
             "year": "2017", "lang": "Tamil"}],
        # ...and only under the shortened title, which the whole-title scan
        # never asks for
        ("Baahubali", "telugu"): [
            {"id": "yKue", "title": "Baahubali 2", "year": "2017",
             "lang": "Telugu"}],
    }

    def setUp(self):
        einthusan_source._found.clear()
        self.real_page = einthusan_source._page
        einthusan_source._page = lambda term, lang: self.PAGES.get(
            (term, lang), [])

    def tearDown(self):
        einthusan_source._page = self.real_page
        einthusan_source._found.clear()

    def test_every_language_is_kept_in_index_order(self):
        found = einthusan_source.find("RRR", 2022)
        self.assertEqual(list(found["by_lang"]),
                         ["tamil", "telugu", "hindi"])
        self.assertEqual(found["by_lang"]["telugu"]["id"], "35hu")

    def test_preference_only_applies_when_the_index_exists(self):
        self.assertEqual(
            einthusan_source.find("RRR", 2022, prefer="telugu")["pick"],
            "telugu")
        self.assertEqual(
            einthusan_source.find("RRR", 2022, prefer="kannada")["pick"],
            "tamil")

    def test_a_film_that_is_not_there_is_not_invented(self):
        self.assertIsNone(einthusan_source.find("Nothing Here", 1999))


class LanguageParsing(unittest.TestCase):
    """Reading the language out of a Wikipedia film article."""

    def test_list_template_keeps_its_languages(self):
        self.assertEqual(
            language._first_language(language._clean("{{ubl|Hindi|Marathi}}")),
            "hindi")

    def test_a_citation_cannot_lend_its_language(self):
        page = ('<ref name="x">{{cite web|url=https://example.com|'
                'language=en}}</ref>\n{{Infobox film\n| name = Tumbbad\n'
                '| language = {{ubl|Hindi|Marathi}}\n}}')
        field = language._FIELD.search(language._REF.sub(" ", page))
        self.assertIsNotNone(field)
        self.assertEqual(
            language._first_language(language._clean(field.group(1))),
            "hindi")

    def test_non_film_articles_are_skipped(self):
        self.assertTrue(language._NOT_THE_FILM.search("Tumbbad (soundtrack)"))
        self.assertFalse(language._NOT_THE_FILM.search("Vikram (2022 film)"))

    def test_original_reads_the_infobox(self):
        def fake_get(params):
            if params.get("list") == "search":
                return {"query": {"search": [{"title": "RRR"}]}}
            return {"parse": {"wikitext":
                              "{{Infobox film\n| language = Telugu\n}} 2022"}}

        real = language._get
        language._get = fake_get
        language._cache.clear()
        try:
            self.assertEqual(language.original("RRR", 2022), "telugu")
        finally:
            language._get = real
            language._cache.clear()

    def test_a_page_without_the_film_is_not_used(self):
        def fake_get(params):
            if params.get("list") == "search":
                return {"query": {"search": [{"title": "Something Else"}]}}
            raise AssertionError("should not read a page")

        real = language._get
        language._get = fake_get
        language._cache.clear()
        try:
            self.assertEqual(language.original("RRR", 2022), "")
        finally:
            language._get = real
            language._cache.clear()


class OriginalLanguage(unittest.TestCase):
    """The frame plays the film's own language, not a dub of it."""

    def setUp(self):
        self.real_find = einthusan_source.find
        self.real_original = einthusan_source.language.original
        einthusan_source.find = lambda name, year, prefer="": {
            "by_lang": {"tamil": {"id": "t4m1", "lang": "Tamil"},
                        "telugu": {"id": "t3l2", "lang": "Telugu"}},
            "pick": "tamil",
        }

    def tearDown(self):
        einthusan_source.find = self.real_find
        einthusan_source.language.original = self.real_original

    def test_the_original_index_is_played(self):
        einthusan_source.language.original = lambda name, year: "telugu"
        played = einthusan_source.play("RRR", 2022)
        self.assertEqual(played["code"], "telugu")
        self.assertEqual(played["record"]["id"], "t3l2")

    def test_the_only_copy_plays_when_the_original_index_is_missing(self):
        einthusan_source.language.original = lambda name, year: "hindi"
        played = einthusan_source.play("RRR", 2022)
        self.assertEqual(played["code"], "tamil")
        self.assertEqual(played["original"], "hindi")

    def test_no_index_at_all_plays_nothing(self):
        einthusan_source.find = lambda name, year, prefer="": None
        self.assertIsNone(einthusan_source.play("Nothing", 2020))


class Merge(unittest.TestCase):
    """Two devices, one account: the newer write wins, nothing is lost."""

    def test_newest_resume_wins(self):
        merged = sync.merge(
            {"progress": {"ext:movie:tt1": {"at": 2000, "seconds": 90,
                                           "duration": 600}}},
            {"progress": {"ext:movie:tt1": {"at": 1000, "seconds": 30,
                                           "duration": 600}}})
        self.assertEqual(merged["progress"]["ext:movie:tt1"]["seconds"], 90)

    def test_one_entry_per_film(self):
        merged = sync.merge(
            {"watchlist": [{"id": "tt1", "at": 1000}]},
            {"watchlist": [{"id": "tt1", "at": 2000}]})
        self.assertEqual(len(merged["watchlist"]), 1)

    def test_nothing_is_sent_back_for_a_film_that_was_finished(self):
        # the browser stamps in milliseconds; a finish newer than the resume
        # point means the film was completed, so the point is dropped
        now = int(time.time() * 1000)
        merged = sync.merge(
            {"progress": {"ext:movie:tt1": {"at": now - 60000,
                                           "seconds": 600, "duration": 600}},
             "dropped": {"ext:movie:tt1": now - 30000}},
            {})
        self.assertNotIn("ext:movie:tt1", merged["progress"])


if __name__ == "__main__":
    unittest.main()
