# -*- coding: utf-8 -*-
"""
Abstrakacja dla AI providerów - lokalnych i zewnętrznych.
Interfejs: OpenAI, Gemini, Ollama, LM Studio
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import requests
import json

from .config import logger


class AIProvider(ABC):
    """Interfejs bazowy dla wszystkich AI providerów."""
    
    def __init__(self, name: str):
        self.name = name
        self.enabled = False
    
    @abstractmethod
    def is_available(self) -> bool:
        """Sprawdz czy provider jest dostępny (API key, połączenie itp)."""
        pass
    
    @abstractmethod
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                     temperature: float = 0.7, max_tokens: int = 1000,
                     expects_json: bool = False) -> Optional[str]:
        """Generuj tekst na podstawie prompta.

        expects_json: gdy True, wywolujacy oczekuje ze odpowiedz bedzie
        sparsowana jako JSON (_parse_json_response). Providery ktore maja
        natywny tryb wymuszania poprawnego JSON-a (np. Ollama "format":
        "json") powinny go tu wlaczyc - lokalne, mniejsze modele (jak
        llama3.1:8b) bardzo czesto psuja JSON (nieescape'owane znaki nowej
        linii w stringach, gadatliwy wstep typu "Oto odpowiedz w postaci
        JSON:"), a wymuszenie na poziomie samplingu eliminuje to niemal
        calkowicie, zamiast polegac wylacznie na parsowaniu po fakcie."""
        pass
    
    @abstractmethod
    def check_connection(self) -> bool:
        """Test połączenia z providerem."""
        pass


class OpenAIProvider(AIProvider):
    """OpenAI (ChatGPT) - wymaga API key."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        super().__init__("OpenAI ChatGPT")
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"
    
    def is_available(self) -> bool:
        return bool(self.api_key) and len(self.api_key.strip()) > 0
    
    def check_connection(self) -> bool:
        if not self.is_available():
            return False
        try:
            response = requests.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 10
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.error("OpenAI connection test failed: %s", e)
            return False
    
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                     temperature: float = 0.7, max_tokens: int = 1000,
                     expects_json: bool = False) -> Optional[str]:
        if not self.is_available():
            return None
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if expects_json:
            payload["response_format"] = {"type": "json_object"}

        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
            else:
                logger.error("OpenAI error: %s", response.text)
        except Exception as e:
            logger.error("OpenAI generation failed: %s", e)
        
        return None


class GeminiProvider(AIProvider):
    """Google Gemini - wymaga API key."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-pro"):
        super().__init__("Google Gemini")
        self.api_key = api_key
        self.model = model
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    
    def is_available(self) -> bool:
        return bool(self.api_key) and len(self.api_key.strip()) > 0
    
    def check_connection(self) -> bool:
        if not self.is_available():
            return False
        try:
            response = requests.post(
                self.api_url,
                params={"key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": "test"}]}],
                    "generationConfig": {"maxOutputTokens": 10}
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            logger.error("Gemini connection test failed: %s", e)
            return False
    
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                     temperature: float = 0.7, max_tokens: int = 1000,
                     expects_json: bool = False) -> Optional[str]:
        if not self.is_available():
            return None
        
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        generation_config = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens
        }
        if expects_json:
            generation_config["response_mime_type"] = "application/json"

        try:
            response = requests.post(
                self.api_url,
                params={"key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": full_prompt}]}],
                    "generationConfig": generation_config
                },
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    if "content" in data["candidates"][0]:
                        parts = data["candidates"][0]["content"].get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
            else:
                logger.error("Gemini error: %s", response.text)
        except Exception as e:
            logger.error("Gemini generation failed: %s", e)
        
        return None


class OllamaProvider(AIProvider):
    """Ollama - lokalne modele (Llama2, Mistral itp)."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama2"):
        super().__init__("Ollama (Local)")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_url = f"{self.base_url}/api/generate"
    
    def is_available(self) -> bool:
        return True  # Zawsze możliwe, ale connection check go zwaliduje
    
    def check_connection(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])
                model_names = [m.get("name", "").split(":")[0] for m in models]
                return self.model.split(":")[0] in model_names or any(self.model in name for name in model_names)
            return False
        except Exception as e:
            logger.error("Ollama connection test failed: %s", e)
            return False
    
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                     temperature: float = 0.7, max_tokens: int = 1000,
                     expects_json: bool = False) -> Optional[str]:
        if not self.check_connection():
            return None
        
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"System: {system_prompt}\n\nUser: {prompt}"
        
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "temperature": temperature,
            "num_predict": max_tokens,
            "stream": False
        }
        if expects_json:
            # Wymusza poprawna skladnie JSON na poziomie samplingu (Ollama
            # constrained generation) - eliminuje najczestsze problemy
            # mniejszych lokalnych modeli: gadatliwy wstep przed "{" oraz
            # nieescape'owane znaki nowej linii w wartosciach stringow.
            payload["format"] = "json"

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("response", "").strip()
            else:
                logger.error("Ollama error: %s", response.text)
        except Exception as e:
            logger.error("Ollama generation failed: %s", e)
        
        return None


class LMStudioProvider(AIProvider):
    """LM Studio - lokalne modele (kompatybilne z OpenAI API)."""
    
    def __init__(self, base_url: str = "http://localhost:1234", model: str = "local-model"):
        super().__init__("LM Studio (Local)")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_url = f"{self.base_url}/v1/chat/completions"
    
    def is_available(self) -> bool:
        return True
    
    def check_connection(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error("LM Studio connection test failed: %s", e)
            return False
    
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                     temperature: float = 0.7, max_tokens: int = 1000,
                     expects_json: bool = False) -> Optional[str]:
        if not self.check_connection():
            return None
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if expects_json:
            # Wiekszosc backendow LM Studio (llama.cpp server) honoruje ten
            # sam parametr co OpenAI; jesli dany model/serwer go nie wspiera,
            # pole jest po prostu ignorowane.
            payload["response_format"] = {"type": "json_object"}

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
            else:
                logger.error("LM Studio error: %s", response.text)
        except Exception as e:
            logger.error("LM Studio generation failed: %s", e)
        
        return None


class DeepSeekLaudeProvider(AIProvider):
    """DeepSeekLaude - lokalny bridge (kompatybilny z OpenAI) do darmowego
    czatu DeepSeek, hostowany w projekcie deepseeklaude (server/api.py).
    W przeciwienstwie do LM Studio, ten serwer akceptuje TYLKO konkretne
    nazwy modeli (deepseek-chat / deepseek-expert) - nieznana nazwa modelu
    dostaje 404, wiec (inaczej niz LMStudioProvider) model jest tu
    parametrem, nie stala."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", model: str = "deepseek-chat",
                 web_search: bool = False):
        super().__init__("DeepSeekLaude (Local)")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.web_search = web_search
        self.api_url = f"{self.base_url}/v1/chat/completions"

    def is_available(self) -> bool:
        return True

    def check_connection(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/v1/models", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error("DeepSeekLaude connection test failed: %s", e)
            return False

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                     temperature: float = 0.7, max_tokens: int = 1000,
                     expects_json: bool = False) -> Optional[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # UWAGA: DeepSeekLaude to NIEOFICJALNY bridge do darmowego czatu
        # (przegladarkowy, nie prawdziwe API OpenAI) - w przeciwienstwie do
        # OpenAI/LM Studio/Ollama nie wiadomo, czy jego serwer po prostu
        # zignoruje nieznane pole w body, czy tez zwroci blad walidacji
        # (patrz komentarz w klasie: "akceptuje TYLKO konkretne nazwy
        # modeli", czyli waliduje request scislej niz standardowe API).
        # Dlatego CELOWO nie wysylamy tu "response_format" mimo ze parametr
        # expects_json jest przyjmowany (dla spojnosci interfejsu) - zeby
        # nie zepsuc dzialajacego providera nieprzetestowanym polem.
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "search": self.web_search,
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                # DeepSeek odpowiada przez darmowy czat webowy (nie plyneli API) -
                # bywa zauwazalnie wolniejsze niz zwykle lokalne API, stad dluzszy timeout.
                # Z wlaczonym web_search moze byc jeszcze wolniej (dochodzi realne
                # przeszukiwanie internetu przed odpowiedzia).
                timeout=150 if self.web_search else 120
            )

            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
            elif response.status_code == 404:
                logger.error(
                    "DeepSeekLaude: nieznany model '%s'. Sprawdz ze deepseeklaude dziala "
                    "i uzyj 'deepseek-chat' lub 'deepseek-expert'.", self.model
                )
            elif response.status_code == 429:
                logger.warning("DeepSeekLaude: przekroczono limit zapytan (rate limit).")
            else:
                logger.error("DeepSeekLaude error: %s", response.text)
        except Exception as e:
            logger.error("DeepSeekLaude generation failed: %s", e)

        return None


class AIManager:
    """Manager dla wszystkich AI providerów."""
    
    def __init__(self):
        self.providers: Dict[str, AIProvider] = {}
        self.active_provider: Optional[str] = None
    
    def register_provider(self, provider_id: str, provider: AIProvider):
        """Zarejestruj provider."""
        self.providers[provider_id] = provider
        logger.info("AI Provider registered: %s (%s)", provider_id, provider.name)
    
    def set_active_provider(self, provider_id: str) -> bool:
        """Ustaw aktywny provider."""
        if provider_id not in self.providers:
            logger.warning("Provider %s not registered", provider_id)
            return False
        if not self.providers[provider_id].is_available():
            logger.warning("Provider %s not available", provider_id)
            return False
        self.active_provider = provider_id
        logger.info("Active AI provider set to: %s", provider_id)
        return True
    
    def get_active_provider(self) -> Optional[AIProvider]:
        """Pobierz aktywny provider."""
        if not self.active_provider or self.active_provider not in self.providers:
            return None
        return self.providers[self.active_provider]
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None,
                temperature: float = 0.7, max_tokens: int = 1000,
                expects_json: bool = False) -> Optional[str]:
        """Generuj tekst używając aktywnego providera.

        expects_json: przekaz True gdy wynik bedzie parsowany jako JSON
        (patrz _parse_json_response w ai_features.py) - provider moze wtedy
        wymusic poprawna skladnie na poziomie samplingu zamiast liczyc na to,
        ze model "grzecznie" zwroci sam obiekt bez ozdobnikow."""
        provider = self.get_active_provider()
        if not provider:
            logger.warning("No active AI provider")
            return None
        return provider.generate_text(prompt, system_prompt, temperature, max_tokens, expects_json)
    
    def get_available_providers(self) -> List[str]:
        """Pobierz listę dostępnych providerów."""
        return [
            pid for pid, provider in self.providers.items()
            if provider.is_available()
        ]
    
    def get_provider_names(self) -> Dict[str, str]:
        """Pobierz nazwy wszystkich providerów."""
        return {pid: provider.name for pid, provider in self.providers.items()}


# Globalny manager
ai_manager = AIManager()
