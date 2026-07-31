# -*- coding: utf-8 -*-
import time
from typing import Dict, List, Optional

from PySide6.QtCore import QThread, Signal

from .. import database as db
from ..config import logger
from ..scraping import search_companies_web
from ..ai_features import LeadScorer
from ..signal_bus import bus

class SearchWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    result = Signal(list)
    finished = Signal()
    error = Signal(str)
    live_result = Signal(dict)

    def __init__(self, queries: List[str], locations: List[str],
                 limit_per_query: int = 10, czas_szukania: int = 0,
                 proxies: Optional[List[str]] = None,
                 ai_scoring: bool = False, force_research: bool = False):
        super().__init__()
        self.queries = queries
        self.locations = locations
        self.limit_per_query = limit_per_query
        self.czas_szukania = czas_szukania
        self.proxies = proxies or []
        self._stop = False
        self._is_running = True
        self.domain_cache: Dict[str, str] = db.get_scanned_domains()
        self.ai_scoring = ai_scoring
        self.force_research = force_research
        self.searched_combos = set() if force_research else db.get_searched_combos()

    def stop(self):
        self._stop = True
        self._is_running = False

    def run(self):
        all_results = []
        start_time = time.time()
        total = len(self.queries) * len(self.locations)
        processed = 0
        skipped_already_done = 0

        for query in self.queries:
            if self._stop:
                break
            for location in self.locations:
                if self._stop:
                    self.status.emit("⏹️ Zatrzymano")
                    break
                if self.czas_szukania > 0:
                    elapsed_min = (time.time() - start_time) / 60
                    if elapsed_min >= self.czas_szukania:
                        self.status.emit(f"⏰ Upłynął czas ({self.czas_szukania} min)")
                        self._stop = True
                        break

                if (query, location) in self.searched_combos:
                    skipped_already_done += 1
                    processed += 1
                    self.progress.emit(int(processed / total * 100) if total else 0)
                    continue

                self.status.emit(f"🔍 Szukam: {query} w {location}")
                try:
                    results, newly_scanned = search_companies_web(
                        query, location, self.limit_per_query, self,
                        domain_cache=self.domain_cache, proxies=self.proxies
                    )
                    all_results.extend(results)

                    scored_count = 0
                    if self.ai_scoring:
                        for r in results:
                            email = r.get('email', '')
                            if not email: continue
                            lead_id = db.add_lead(
                                r.get('name', ''), email, r.get('address', ''),
                                '', r.get('website', ''), r.get('category', ''),
                                lead_score=-1, lead_score_reason="oczekuje na ocenę AI",
                                linkedin=r.get('linkedin', '')
                            )
                            if not lead_id: continue
                            r['lead_id'] = lead_id
                            try:
                                score_data = LeadScorer.score_lead(
                                    r.get('name', ''), email, r.get('category', ''), r.get('website', '')
                                )
                            except Exception as e:
                                logger.warning("Błąd oceny AI dla %s: %s", email, e)
                                score_data = None

                            if score_data:
                                score = int(score_data.get('score', -1))
                                reason = score_data.get('reason', '')
                                if score_data.get('is_spam'):
                                    reason = f"[SPAM] {reason}".strip()
                                db.update_lead_score(lead_id, score, reason)
                                r['lead_score'] = score
                                r['lead_score_reason'] = reason
                                scored_count += 1
                            else:
                                db.update_lead_score(lead_id, -1, "Błąd oceny AI")

                    for r in results:
                        self.live_result.emit(r)
                    if newly_scanned:
                        self.domain_cache.update(newly_scanned)
                        db.mark_domains_scanned(newly_scanned)
                    db.mark_combo_searched(query, location)
                    self.searched_combos.add((query, location))
                    status_msg = f"✅ Znaleziono {len(results)} firm"
                    if self.ai_scoring:
                        status_msg += f" (oceniono AI: {scored_count}/{len(results)})"
                    self.status.emit(status_msg)
                    bus.leads_changed.emit()
                except Exception as e:
                    logger.exception("Błąd wyszukiwania %s / %s", query, location)
                    self.error.emit(f"❌ Błąd: {e}")

                processed += 1
                self.progress.emit(int((processed / total) * 100) if total else 100)
                time.sleep(0.5)

        self.result.emit(all_results)
        self.finished.emit()
