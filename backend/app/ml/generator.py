# Изоляция ML-логики — весь код работы с моделью инкапсулирован здесь
# Логирование — время каждого этапа работы с моделью
# Управление ресурсами — ограничения по токенам, таймаут инференса
import logging
import time
from dataclasses import dataclass

import requests

from app.config import settings

logger = logging.getLogger(__name__)

# Системный промпт для задачи суммаризации/генерации
_SUMMARIZE_TEMPLATE = (
    "You are a helpful assistant. Summarize the following text concisely.\n\n"
    "Text:\n{prompt}\n\nSummary:"
)


@dataclass
class GenerationResult:
    text: str
    inference_time: float


class TextGenerator:
    """
    Изоляция ML-логики — инкапсулирует вызовы к Ollama REST API.
    API вызывает только метод generate(). Никакой ML-логики в роутерах.
    Ollama работает локально — нет зависимости от внешней сети.
    """

    def __init__(self) -> None:
        self._base_url = settings.OLLAMA_URL.rstrip("/")
        self._model = settings.OLLAMA_MODEL
        # Управление ресурсами — жёсткий потолок токенов и таймаут
        self._max_tokens = settings.MAX_NEW_TOKENS
        self._timeout = settings.INFERENCE_TIMEOUT
        self._ready = False

    def warmup(self) -> None:
        """Прогрев: проверяем доступность Ollama и наличие модели."""
        logger.info("Checking Ollama at %s (model=%s) ...", self._base_url, self._model)
        try:
            resp = requests.get(f"{self._base_url}/api/tags", timeout=10)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                logger.info("Ollama available. Models: %s", models)
                self._ready = True
            else:
                logger.warning("Ollama returned status=%d", resp.status_code)
                self._ready = True  # не блокируем старт
        except Exception as exc:
            logger.warning("Ollama warmup failed: %s", exc)
            self._ready = True

    @property
    def is_ready(self) -> bool:
        return self._ready

    def generate(self, prompt: str, max_tokens: int, creativity: float) -> GenerationResult:
        """
        Изоляция ML-логики — единственный публичный метод генерации.
        Управление ресурсами — ограничения max_tokens и таймаут.
        Логирование — начало и конец инференса.
        """
        # Управление ресурсами — не превышаем системный максимум
        effective_max_tokens = min(max_tokens, self._max_tokens)
        full_prompt = _SUMMARIZE_TEMPLATE.format(prompt=prompt)

        payload = {
            "model": self._model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "num_predict": effective_max_tokens,
                "temperature": float(creativity) if creativity > 0 else 0.0,
                "top_p": 0.9,
            },
        }

        logger.info(
            "Inference start | model=%s | prompt_len=%d | max_tokens=%d | creativity=%.2f",
            self._model,
            len(prompt),
            effective_max_tokens,
            creativity,
        )

        t_start = time.perf_counter()
        try:
            # Управление ресурсами — таймаут на инференс
            response = requests.post(
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=self._timeout,
            )
        except requests.Timeout:
            raise RuntimeError(f"Inference timed out after {self._timeout}s")
        except requests.ConnectionError as exc:
            raise RuntimeError(f"Cannot connect to Ollama at {self._base_url}: {exc}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        inference_time = time.perf_counter() - t_start

        if response.status_code == 404:
            raise RuntimeError(
                f"Model '{self._model}' not found in Ollama. "
                f"Run: docker exec <ollama-container> ollama pull {self._model}"
            )
        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama error {response.status_code}: {response.text[:200]}"
            )

        data = response.json()
        generated_text = data.get("response", "").strip()

        logger.info(
            "Inference end | inference_time=%.3fs | result_len=%d",
            inference_time,
            len(generated_text),
        )

        return GenerationResult(text=generated_text, inference_time=inference_time)


# Синглтон — единственный экземпляр на процесс
generator = TextGenerator()
