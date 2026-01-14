# FILE: hmi_pages/hmi_charts.py
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from data_sys.stat import StatManager
from root import config as cfg

def render_charts_page():
    """
    Отрисовка графиков доходности. 
    Список пар берется автоматически из config.ACTIVE_AGENTS_IDS.
    """
    st.header("📈 Анализ кривых доходности и стратегий")
    
    symbol_tf_list = cfg.ACTIVE_AGENTS_IDS
    stat_mgr = StatManager()
    
    # Инициализация настроек визуализации в session_state, если их нет
    if 'chart_settings' not in st.session_state:
        st.session_state.chart_settings = {
            'visibility': {aid: True for aid in symbol_tf_list},
            'colors': {aid: "#00FFAA" for aid in symbol_tf_list}
        }

    # Боковая панель управления визуализацией
    with st.sidebar.expander("🎨 Настройка графиков", expanded=True):
        for aid in symbol_tf_list:
            col1, col2 = st.columns([3, 1])
            
            # Управление видимостью
            st.session_state.chart_settings['visibility'][aid] = col1.checkbox(
                f"{aid}", 
                value=st.session_state.chart_settings['visibility'].get(aid, True),
                key=f"vis_{aid}"
            )
            
            # Выбор цвета
            st.session_state.chart_settings['colors'][aid] = col2.color_picker(
                "Цвет", 
                value=st.session_state.chart_settings['colors'].get(aid, "#00FFAA"),
                key=f"cp_{aid}",
                label_visibility="collapsed"
            )
        
        if st.button("🔄 Сбросить стили", use_container_width=True):
            st.session_state.pop('chart_settings')
            st.rerun()

    # Выбор периода данных для анализа
    time_range = st.select_slider(
        "Глубина анализа сделок", 
        options=["Неделя", "Месяц", "Квартал", "Год"], 
        value="Месяц"
    )
    days_map = {"Неделя": 7, "Месяц": 30, "Квартал": 90, "Год": 365}

    fig = go.Figure()
    
    # Отрисовка кривых доходности
    for aid in symbol_tf_list:
        # Проверяем, включен ли график пользователем
        if st.session_state.chart_settings['visibility'].get(aid):
            # Получаем историю торгов через StatManager
            df, _ = stat_mgr.get_trades_history(symbol=aid, days=days_map[time_range])
            
            if df is not None and not df.empty:
                df = df.sort_index()
                # Рассчитываем кумулятивную прибыль
                df['cum_profit'] = df['profit'].cumsum()
                
                fig.add_trace(go.Scatter(
                    x=df.index, 
                    y=df['cum_profit'],
                    name=aid,
                    mode='lines',
                    line=dict(color=st.session_state.chart_settings['colors'].get(aid), width=2.5),
                    hovertemplate=f"<b>{aid}</b><br>Дата: %{{x}}<br>Equity: %{{y:.2f}} USD<extra></extra>",
                ))

    # Настройка темной темы Plotly
    fig.update_layout(
        xaxis=dict(
            title="Дата и время закрытия", 
            gridcolor="#333",
            rangeslider=dict(visible=True),
            type='date'
        ),
        yaxis=dict(
            title="Equity (USD)", 
            gridcolor="#333",
            zerolinecolor="#666",
            tickformat=".2f"
        ),
        hovermode="x unified",
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=50, b=0)
    )

    if len(fig.data) > 0:
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': True})
    else:
        st.warning(f"Нет данных для отображения за период: {time_range}")
    
    st.info("💡 Используйте Range Slider внизу для детального изучения просадок.")
