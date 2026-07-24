# -*- coding: utf-8 -*-
"""
Worker thread dla AI - asynchroniczne operacje.
"""
from typing import Optional, Dict, Any, Callable
from PySide6.QtCore import QThread, Signal

from .config import logger
from .ai_features import (
    TemplateGenerator, SubjectLineOptimizer, LeadPersonalizer,
    LeadScorer, ResponseAnalyzer, SendTimingOptimizer, ABTestingEngine
)


class AIWorker(QThread):
    """Worker thread dla AI operacji."""
    
    # Sygnały
    result = Signal(dict)  # {"status": "success"/"error", "data": {...}}
    progress = Signal(str)  # komunikat postępu
    finished = Signal()
    error = Signal(str)
    
    def __init__(self):
        super().__init__()
        self._stop = False
        self.task_queue = []
    
    def stop(self):
        self._stop = True
    
    def add_task(self, task_type: str, **kwargs):
        """Dodaj zadanie do kolejki."""
        self.task_queue.append({"type": task_type, "params": kwargs})
    
    def run(self):
        """Wykonuj zadania z kolejki."""
        while self.task_queue and not self._stop:
            task = self.task_queue.pop(0)
            try:
                result = self._execute_task(task)
                self.result.emit(result)
            except Exception as e:
                logger.error("AI Worker task error: %s", e)
                self.error.emit(str(e))
        
        self.finished.emit()
    
    def _execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Wykonaj jedno zadanie."""
        task_type = task.get("type", "")
        params = task.get("params", {})
        
        # Template generation
        if task_type == "generate_templates":
            self.progress.emit("Generuję szablony...")
            templates = TemplateGenerator.generate(
                params.get("industry", ""),
                params.get("product", ""),
                params.get("tone", "professional")
            )
            return {"status": "success", "data": {"templates": templates}, "type": task_type}
        
        # Subject line optimization
        elif task_type == "generate_subject_lines":
            self.progress.emit("Generuję subject lines...")
            variants = SubjectLineOptimizer.generate_variants(
                params.get("topic", ""),
                params.get("industry", ""),
                params.get("count", 5)
            )
            return {"status": "success", "data": {"variants": variants}, "type": task_type}
        
        elif task_type == "score_subject_line":
            self.progress.emit("Oceniam subject line...")
            score = SubjectLineOptimizer.score_subject_line(params.get("subject", ""))
            return {"status": "success", "data": {"score": score}, "type": task_type}
        
        # Lead personalization
        elif task_type == "analyze_website":
            self.progress.emit("Analizuję website...")
            insights = LeadPersonalizer.analyze_website(
                params.get("company_name", ""),
                params.get("website", ""),
                params.get("industry", "")
            )
            return {"status": "success", "data": {"insights": insights}, "type": task_type}
        
        elif task_type == "personalize_message":
            self.progress.emit("Personalizuję wiadomość...")
            message = LeadPersonalizer.personalize_message(
                params.get("template", ""),
                params.get("lead", {}),
                params.get("website_insights")
            )
            return {"status": "success", "data": {"message": message}, "type": task_type}
        
        # Lead scoring
        elif task_type == "score_lead":
            self.progress.emit("Oceniam lead...")
            score_data = LeadScorer.score_lead(
                params.get("company_name", ""),
                params.get("email", ""),
                params.get("industry", ""),
                params.get("website", "")
            )
            return {"status": "success", "data": {"score_data": score_data}, "type": task_type}
        
        # Response analysis
        elif task_type == "analyze_response":
            self.progress.emit("Analizuję odpowiedź...")
            analysis = ResponseAnalyzer.classify_response(params.get("email_body", ""))
            return {"status": "success", "data": {"analysis": analysis}, "type": task_type}
        
        # Timing optimization
        elif task_type == "get_send_timing":
            self.progress.emit("Obliczam optymalny czas wysyłki...")
            timing = SendTimingOptimizer.recommend_send_time(
                params.get("industry", ""),
                params.get("region", ""),
                params.get("target_role", "manager")
            )
            return {"status": "success", "data": {"timing": timing}, "type": task_type}
        
        # A/B testing
        elif task_type == "generate_ab_variants":
            self.progress.emit("Generuję warianty A/B...")
            variants = ABTestingEngine.generate_variants(
                params.get("content_type", ""),
                params.get("original", ""),
                params.get("count", 2)
            )
            return {"status": "success", "data": {"variants": variants}, "type": task_type}
        
        elif task_type == "analyze_ab_results":
            self.progress.emit("Analizuję wyniki A/B...")
            analysis = ABTestingEngine.analyze_test_results(
                params.get("variant_a", ""),
                params.get("variant_b", ""),
                params.get("results_a", {}),
                params.get("results_b", {})
            )
            return {"status": "success", "data": {"analysis": analysis}, "type": task_type}
        
        else:
            return {"status": "error", "data": {"error": f"Unknown task type: {task_type}"}, "type": task_type}


class BatchAIWorker(QThread):
    """Worker dla batch operacji na wielu leadach."""
    
    progress = Signal(int, int)  # current, total
    lead_result = Signal(str, dict)  # email, result
    finished = Signal()
    error = Signal(str)
    
    def __init__(self, leads: list, operation: str, **kwargs):
        super().__init__()
        self.leads = leads
        self.operation = operation
        self.kwargs = kwargs
        self._stop = False
    
    def stop(self):
        self._stop = True
    
    def run(self):
        """Wykonuj operację na każdym leadzie."""
        total = len(self.leads)
        
        for i, lead in enumerate(self.leads):
            if self._stop:
                break
            
            try:
                if self.operation == "score":
                    result = self._score_lead(lead)
                elif self.operation == "personalize":
                    result = self._personalize_lead(lead)
                elif self.operation == "analyze":
                    result = self._analyze_lead(lead)
                else:
                    result = {"error": f"Unknown operation: {self.operation}"}
                
                email = lead.get("email", "")
                self.lead_result.emit(email, result)
            except Exception as e:
                logger.error("Batch AI operation error for lead %s: %s", lead.get("email"), e)
            
            self.progress.emit(i + 1, total)
        
        self.finished.emit()
    
    def _score_lead(self, lead: dict) -> dict:
        """Oceń lead."""
        score_data = LeadScorer.score_lead(
            lead.get("firma", ""),
            lead.get("email", ""),
            self.kwargs.get("industry", ""),
            lead.get("website", "")
        )
        return {"type": "score", "data": score_data}
    
    def _personalize_lead(self, lead: dict) -> dict:
        """Personalizuj dla leadу."""
        insights = self.kwargs.get("insights", {})
        message = LeadPersonalizer.personalize_message(
            self.kwargs.get("template", ""),
            lead,
            insights.get(lead.get("email"))
        )
        return {"type": "personalize", "data": {"message": message}}
    
    def _analyze_lead(self, lead: dict) -> dict:
        """Analizuj leadу."""
        insights = LeadPersonalizer.analyze_website(
            lead.get("firma", ""),
            lead.get("website", ""),
            self.kwargs.get("industry", "")
        )
        return {"type": "analyze", "data": {"insights": insights}}
