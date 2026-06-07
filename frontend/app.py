# Визуальный интерфейс сервиса — обращается к /api/generate, /api/history, /api/health
# Слабая связность — только через REST API (requests), никаких прямых импортов бэкенда
# Изоляция в сети — не обращается к БД или Redis напрямую
# Обработка сбоев — красивые уведомления при ошибках
# UX асинхронности — спиннер во время выполнения задачи
# Визуальная репрезентация — графики истории инференса и длин текстов
import time

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# Слабая связность — URL бэкенда через переменную окружения или хардкод для Docker
import os

API_BASE = os.getenv("API_BASE_URL", "http://api:8000")
POLL_INTERVAL = 1.5  # секунды между проверкой статуса задачи


# Обработка сбоев — вспомогательная функция для безопасных запросов
def safe_get(url: str, **kwargs) -> requests.Response | None:
    """Возвращает None при любой ошибке соединения."""
    try:
        return requests.get(url, timeout=10, **kwargs)
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.Timeout:
        return None
    except Exception:
        return None


def safe_post(url: str, **kwargs) -> requests.Response | None:
    try:
        return requests.post(url, timeout=15, **kwargs)
    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.Timeout:
        return None
    except Exception:
        return None


st.set_page_config(
    page_title="ML Text Generation Service",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Боковая панель: Health Status ─────────────────────────────────────────────
# Визуальный интерфейс сервиса — GET /api/health
with st.sidebar:
    st.title("🤖 ML Service")
    st.markdown("---")
    st.subheader("Health Status")

    if st.button("Refresh Status"):
        st.rerun()

    health_resp = safe_get(f"{API_BASE}/api/health")
    if health_resp is None:
        # Обработка сбоев — уведомление вместо трейсбека
        st.error("❌ Сервис временно недоступен")
        st.warning("Проверьте, что бэкенд запущен (`docker compose up`)")
    elif health_resp.status_code == 200:
        health_data = health_resp.json()
        overall = health_data.get("status", "unknown")
        icon = "✅" if overall == "ok" else "⚠️" if overall == "degraded" else "❌"
        st.markdown(f"**Общий статус:** {icon} `{overall}`")

        for component, info in health_data.get("components", {}).items():
            c_status = info.get("status", "unknown")
            c_icon = "✅" if c_status == "ok" else "❌"
            detail = info.get("detail", "")
            label = f"{c_icon} **{component}**"
            if detail:
                label += f" — `{detail[:40]}`"
            st.markdown(label)
    else:
        # Обработка сбоев — показываем HTTP статус
        st.error(f"❌ Health check failed: HTTP {health_resp.status_code}")

    st.markdown("---")
    st.caption("v1.0.0 | HuggingFace API")

# ── Вкладки ────────────────────────────────────────────────────────────────────
tab_generate, tab_history, tab_stats = st.tabs(["✍️ Генерация", "📜 История", "📊 Статистика"])

# ── Вкладка 1: Генерация ───────────────────────────────────────────────────────
with tab_generate:
    st.header("Генерация текста")
    st.markdown("Введите текст для обработки моделью `ollama/tinyllama`.")

    prompt = st.text_area(
        "Текст для обработки",
        height=200,
        placeholder="Paste a long article or text here to summarize...",
        help="Минимум 10, максимум 4096 символов",
    )

    col1, col2 = st.columns(2)
    with col1:
        max_tokens = st.slider("Максимум токенов", min_value=10, max_value=512, value=128, step=10)
    with col2:
        creativity = st.slider(
            "Creativity (температура)", min_value=0.0, max_value=1.0, value=0.5, step=0.05
        )

    if len(prompt.strip()) < 10:
        st.caption("Введите не менее 10 символов для активации кнопки.")

    if st.button("🚀 Отправить задачу", type="primary"):
        if len(prompt.strip()) < 10:
            st.warning("Текст слишком короткий — минимум 10 символов.")
            st.stop()
        # Визуальный интерфейс сервиса — POST /api/generate
        resp = safe_post(
            f"{API_BASE}/api/generate",
            json={"prompt": prompt, "max_tokens": max_tokens, "creativity": creativity},
        )

        if resp is None:
            # Обработка сбоев — понятное сообщение
            st.error("❌ Сервис временно недоступен. Попробуйте позже.")
        elif resp.status_code == 503:
            st.error("❌ Сервис перегружен (503). Попробуйте через несколько секунд.")
        elif resp.status_code == 422:
            st.error(f"❌ Ошибка валидации: {resp.json().get('detail', resp.text)}")
        elif resp.status_code == 202:
            task_id = resp.json()["task_id"]
            st.info(f"✅ Задача поставлена в очередь. ID: `{task_id}`")

            # UX асинхронности — спиннер и polling до завершения задачи
            result_placeholder = st.empty()
            progress_placeholder = st.empty()

            with result_placeholder.container():
                with st.spinner("⏳ Выполняется инференс... Пожалуйста, подождите"):
                    for attempt in range(120):  # максимум 3 минуты
                        status_resp = safe_get(f"{API_BASE}/api/tasks/{task_id}")

                        if status_resp is None:
                            st.error("❌ Потеряно соединение с сервером")
                            break

                        task_data = status_resp.json()
                        task_status = task_data.get("status", "PENDING")

                        progress_placeholder.caption(
                            f"Статус: `{task_status}` | Попытка {attempt + 1}"
                        )

                        if task_status == "SUCCESS":
                            progress_placeholder.empty()
                            st.success("✅ Генерация завершена!")
                            st.markdown("**Результат:**")
                            st.text_area(
                                "",
                                value=task_data.get("result", ""),
                                height=150,
                                key=f"result_{task_id}",
                            )
                            inf_time = task_data.get("inference_time")
                            if inf_time:
                                st.caption(f"⏱️ Время инференса: {inf_time:.2f}с")
                            break

                        elif task_status == "FAILURE":
                            progress_placeholder.empty()
                            st.error(
                                f"❌ Ошибка генерации: {task_data.get('error', 'Неизвестная ошибка')}"
                            )
                            break

                        time.sleep(POLL_INTERVAL)
                    else:
                        st.warning("⚠️ Превышено время ожидания. Проверьте статус вручную.")
        else:
            st.error(f"❌ Неожиданный ответ: HTTP {resp.status_code} — {resp.text[:200]}")

# ── Вкладка 2: История ─────────────────────────────────────────────────────────
with tab_history:
    st.header("История генераций")

    col_page, col_size = st.columns([1, 1])
    with col_page:
        page = st.number_input("Страница", min_value=1, value=1, step=1)
    with col_size:
        page_size = st.selectbox("Записей на странице", [10, 20, 50], index=1)

    # Визуальный интерфейс сервиса — GET /api/history
    hist_resp = safe_get(f"{API_BASE}/api/history", params={"page": page, "page_size": page_size})

    if hist_resp is None:
        # Обработка сбоев
        st.error("❌ Сервис временно недоступен")
    elif hist_resp.status_code == 200:
        hist_data = hist_resp.json()
        items = hist_data.get("items", [])
        total = hist_data.get("total", 0)

        st.caption(f"Всего записей: **{total}**")

        if not items:
            st.info("Пока нет истории генераций. Создайте первую задачу!")
        else:
            for item in items:
                status_icon = {"SUCCESS": "✅", "FAILURE": "❌", "PENDING": "⏳", "STARTED": "🔄"}.get(
                    item["status"], "❓"
                )
                with st.expander(
                    f"{status_icon} `{item['task_id'][:12]}...` | {item['created_at'][:19]}"
                ):
                    st.markdown(f"**Статус:** `{item['status']}`")
                    st.markdown(f"**Промпт:** {item['prompt'][:200]}{'...' if len(item['prompt']) > 200 else ''}")
                    if item.get("result"):
                        st.markdown(f"**Результат:** {item['result'][:300]}{'...' if len(item.get('result','')) > 300 else ''}")
                    if item.get("inference_time"):
                        st.markdown(f"**Время инференса:** {item['inference_time']:.2f}с")
                    st.markdown(
                        f"**Параметры:** max_tokens={item['max_tokens']}, creativity={item['creativity']}"
                    )
    else:
        st.error(f"❌ Ошибка загрузки истории: HTTP {hist_resp.status_code}")

# ── Вкладка 3: Статистика / Визуальная репрезентация ──────────────────────────
with tab_stats:
    # Визуальная репрезентация — графики на основе данных истории
    st.header("Статистика и графики")

    all_resp = safe_get(f"{API_BASE}/api/history", params={"page": 1, "page_size": 100})

    if all_resp is None:
        st.error("❌ Сервис временно недоступен")
    elif all_resp.status_code == 200:
        all_items = all_resp.json().get("items", [])
        successful = [i for i in all_items if i["status"] == "SUCCESS"]

        if len(successful) < 2:
            st.info("Недостаточно данных для графиков. Создайте несколько генераций!")
        else:
            df = pd.DataFrame(successful)
            df["created_at"] = pd.to_datetime(df["created_at"])
            df["result_len"] = df["result"].apply(lambda x: len(x) if x else 0)
            df["prompt_len"] = df["prompt"].apply(len)

            col_a, col_b = st.columns(2)

            with col_a:
                # Визуальная репрезентация — время инференса по времени
                fig1 = px.line(
                    df.sort_values("created_at"),
                    x="created_at",
                    y="inference_time",
                    title="Время инференса (сек)",
                    labels={"created_at": "Время", "inference_time": "Сек"},
                    markers=True,
                )
                fig1.update_layout(height=300)
                st.plotly_chart(fig1, use_container_width=True)

            with col_b:
                # Визуальная репрезентация — длина сгенерированных текстов
                fig2 = px.histogram(
                    df,
                    x="result_len",
                    nbins=20,
                    title="Распределение длин результатов",
                    labels={"result_len": "Символов"},
                )
                fig2.update_layout(height=300)
                st.plotly_chart(fig2, use_container_width=True)

            col_c, col_d = st.columns(2)
            with col_c:
                # Визуальная репрезентация — распределение creativity
                fig3 = px.histogram(
                    df,
                    x="creativity",
                    nbins=10,
                    title="Распределение параметра Creativity",
                    labels={"creativity": "Creativity"},
                )
                fig3.update_layout(height=300)
                st.plotly_chart(fig3, use_container_width=True)

            with col_d:
                # Визуальная репрезентация — длина промпта vs время инференса
                fig4 = px.scatter(
                    df,
                    x="prompt_len",
                    y="inference_time",
                    title="Длина промпта vs Время инференса",
                    labels={"prompt_len": "Символов в промпте", "inference_time": "Сек"},
                )
                fig4.update_layout(height=300)
                st.plotly_chart(fig4, use_container_width=True)

            # Сводная таблица
            st.subheader("Сводная статистика")
            stats_df = df[["inference_time", "result_len", "prompt_len", "max_tokens", "creativity"]].describe().round(2)
            st.dataframe(stats_df, use_container_width=True)
    else:
        st.error(f"❌ Ошибка: HTTP {all_resp.status_code}")
