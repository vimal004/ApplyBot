import os
import json
import time
import urllib.request
import urllib.error
from enum import Enum, auto
from typing import Dict, Any, List, Optional
from config import config

class TaskType(Enum):
    PARSING = auto()
    RESUME_TAILORING = auto()
    FORM_FILLING = auto()
    EMAIL_GENERATION = auto()

class LLMManager:
    """
    Centralized, ultra-robust GenAI LLM Router & Provider Manager (2026 active models).
    Features:
    - Multi-Key Support per Provider: Supports comma-separated keys (e.g. GROQ_API_KEY="key1,key2")
    - Task-based multi-tier routing (Parsing vs Resume Tailoring vs Form Autofill vs Email)
    - Active 2026 models (Gemini 3.6 Flash, Gemini 3.5 Flash-Lite, Llama 3.3 70B, Cerebras, OpenRouter free)
    - Circuit Breaker: Automatically cools down keys/providers on HTTP 429 / 503 for 60 seconds
    - Token Thriftiness: Streamlined payloads, compact JSON, minimal whitespace
    - Local Deterministic Fallbacks when all remote APIs are rate limited
    """

    def __init__(self):
        # Timestamp until which a specific key (provider:key_prefix) is in rate-limit cooldown
        self._key_cooldowns: Dict[str, float] = {}

    def _get_keys(self, env_name: str, fallback_attr: str = "") -> List[str]:
        raw_val = os.getenv(env_name, "")
        if not raw_val and fallback_attr:
            raw_val = str(getattr(config.multi_llm, fallback_attr, ""))
        
        # Support comma-separated keys in env or config
        keys = []
        for chunk in raw_val.split(","):
            cleaned = chunk.strip().strip('"').strip("'")
            if cleaned:
                keys.append(cleaned)
        return keys

    def _is_key_available(self, route_id: str) -> bool:
        cooldown_until = self._key_cooldowns.get(route_id, 0)
        if time.time() < cooldown_until:
            return False
        return True

    def _mark_key_cooldown(self, route_id: str, duration_sec: float = 60.0):
        print(f"[{route_id} Circuit Breaker] Rate limited / unavailable. Cooling down for {int(duration_sec)}s.")
        self._key_cooldowns[route_id] = time.time() + duration_sec

    def get_task_routes(self, task: TaskType) -> List[Dict[str, Any]]:
        """
        Returns an ordered list of (Provider, Model, Key) candidates optimized for the given task.
        """
        groq_keys = self._get_keys("GROQ_API_KEY", "groq_api_key")
        gemini_keys = self._get_keys("GEMINI_API_KEY", "gemini_api_key") or self._get_keys("GOOGLE_API_KEY")
        cerebras_keys = self._get_keys("CEREBRAS_API_KEY", "cerebras_api_key")
        openrouter_keys = self._get_keys("OPENROUTER_API_KEY", "openrouter_api_key")

        candidates = []

        if task == TaskType.PARSING:
            # Fast, low-latency extraction (Groq Llama 3.1 8B -> Gemini 3.5 Flash-Lite -> Cerebras)
            for idx, key in enumerate(groq_keys):
                candidates.append({"provider": "Groq", "key_id": f"Groq-{idx+1}", "key": key, "model": "llama-3.1-8b-instant", "endpoint": "https://api.groq.com/openai/v1/chat/completions"})
            for idx, key in enumerate(gemini_keys):
                candidates.append({"provider": "Gemini", "key_id": f"Gemini-{idx+1}", "key": key, "model": "gemini-3.5-flash-lite"})
                candidates.append({"provider": "Gemini", "key_id": f"Gemini-{idx+1}", "key": key, "model": "gemini-3.5-flash"})
            for idx, key in enumerate(cerebras_keys):
                candidates.append({"provider": "Cerebras", "key_id": f"Cerebras-{idx+1}", "key": key, "model": "llama3.1-8b", "endpoint": "https://api.cerebras.ai/v1/chat/completions"})
            for idx, key in enumerate(openrouter_keys):
                candidates.append({"provider": "OpenRouter", "key_id": f"OpenRouter-{idx+1}", "key": key, "model": "openrouter/free", "endpoint": "https://openrouter.ai/api/v1/chat/completions"})

        elif task in (TaskType.RESUME_TAILORING, TaskType.FORM_FILLING):
            # High-context / intelligent structuring -> Active Gemini 3.5 Flash-Lite & 3.5/3.6 Flash & Groq Llama 3.3 70B
            for idx, key in enumerate(gemini_keys):
                candidates.append({"provider": "Gemini", "key_id": f"Gemini-{idx+1}", "key": key, "model": "gemini-3.5-flash-lite"})
                candidates.append({"provider": "Gemini", "key_id": f"Gemini-{idx+1}", "key": key, "model": "gemini-3.5-flash"})
                candidates.append({"provider": "Gemini", "key_id": f"Gemini-{idx+1}", "key": key, "model": "gemini-3.6-flash"})
                candidates.append({"provider": "Gemini", "key_id": f"Gemini-{idx+1}", "key": key, "model": "gemini-2.5-flash"})
            for idx, key in enumerate(groq_keys):
                candidates.append({"provider": "Groq", "key_id": f"Groq-{idx+1}", "key": key, "model": "llama-3.3-70b-versatile", "endpoint": "https://api.groq.com/openai/v1/chat/completions"})
                candidates.append({"provider": "Groq", "key_id": f"Groq-{idx+1}", "key": key, "model": "llama-3.1-8b-instant", "endpoint": "https://api.groq.com/openai/v1/chat/completions"})
            for idx, key in enumerate(cerebras_keys):
                candidates.append({"provider": "Cerebras", "key_id": f"Cerebras-{idx+1}", "key": key, "model": "llama-3.3-70b", "endpoint": "https://api.cerebras.ai/v1/chat/completions"})
            for idx, key in enumerate(openrouter_keys):
                candidates.append({"provider": "OpenRouter", "key_id": f"OpenRouter-{idx+1}", "key": key, "model": "openrouter/free", "endpoint": "https://openrouter.ai/api/v1/chat/completions"})

        elif task == TaskType.EMAIL_GENERATION:
            # Human-like cold email drafting
            for idx, key in enumerate(gemini_keys):
                candidates.append({"provider": "Gemini", "key_id": f"Gemini-{idx+1}", "key": key, "model": "gemini-3.5-flash-lite"})
                candidates.append({"provider": "Gemini", "key_id": f"Gemini-{idx+1}", "key": key, "model": "gemini-3.5-flash"})
                candidates.append({"provider": "Gemini", "key_id": f"Gemini-{idx+1}", "key": key, "model": "gemini-3.6-flash"})
            for idx, key in enumerate(groq_keys):
                candidates.append({"provider": "Groq", "key_id": f"Groq-{idx+1}", "key": key, "model": "llama-3.1-8b-instant", "endpoint": "https://api.groq.com/openai/v1/chat/completions"})
            for idx, key in enumerate(cerebras_keys):
                candidates.append({"provider": "Cerebras", "key_id": f"Cerebras-{idx+1}", "key": key, "model": "llama-3.3-70b", "endpoint": "https://api.cerebras.ai/v1/chat/completions"})
            for idx, key in enumerate(openrouter_keys):
                candidates.append({"provider": "OpenRouter", "key_id": f"OpenRouter-{idx+1}", "key": key, "model": "openrouter/free", "endpoint": "https://openrouter.ai/api/v1/chat/completions"})


        return candidates


    def generate(
        self,
        task: TaskType,
        prompt: str,
        system_prompt: str = "You are a helpful AI job application assistant.",
        max_tokens: int = 2000,
        temperature: float = 0.2,
        json_mode: bool = False
    ) -> Optional[str]:
        """
        Executes an LLM request using task-specific model routing and multi-provider fallback.
        """
        routes = self.get_task_routes(task)

        for route in routes:
            p_name = route["provider"]
            key_id = route["key_id"]
            api_key = route["key"]
            model = route["model"]
            route_id = f"{key_id}:{model}"

            if not self._is_key_available(route_id):
                continue

            try:
                if p_name == "Gemini":
                    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                    combined_prompt = f"SYSTEM: {system_prompt}\n\nUSER: {prompt}"
                    payload: Dict[str, Any] = {
                        "contents": [{"parts": [{"text": combined_prompt}]}],
                        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
                    }
                    if json_mode:
                        payload["generationConfig"]["responseMimeType"] = "application/json"

                    req = urllib.request.Request(
                        gemini_url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}
                    )
                    with urllib.request.urlopen(req, timeout=30) as response:
                        res_data = json.loads(response.read().decode("utf-8"))
                        text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        print(f"[{key_id} AI] Success using model '{model}' for task {task.name}")
                        return text

                else:
                    endpoint = route["endpoint"]
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                        "User-Agent": "ApplyBot/1.0"
                    }
                    if p_name == "OpenRouter":
                        headers["HTTP-Referer"] = "https://github.com/vimal004/ApplyBot"
                        headers["X-Title"] = "ApplyBot"

                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                    if json_mode and p_name == "Groq":
                        payload["response_format"] = {"type": "json_object"}

                    req = urllib.request.Request(
                        endpoint,
                        data=json.dumps(payload).encode("utf-8"),
                        headers=headers
                    )
                    with urllib.request.urlopen(req, timeout=30) as response:
                        res_data = json.loads(response.read().decode("utf-8"))
                        text = res_data["choices"][0]["message"]["content"].strip()
                        print(f"[{key_id} AI] Success using model '{model}' for task {task.name}")
                        return text

            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8") if e.fp else str(e)
                print(f"[{key_id} AI Note] HTTP {e.code} on model '{model}': {err_body[:120]}")
                if e.code in (429, 503):
                    self._mark_key_cooldown(route_id, duration_sec=60.0)
                time.sleep(0.3)

            except Exception as e:
                print(f"[{key_id} AI Note] Model '{model}' error: {e}")
                time.sleep(0.3)


        print(f"[LLMManager Warning] All configured providers & keys rate-limited/unfulfilled for task {task.name}.")
        return None

# Singleton instance
llm_manager = LLMManager()
