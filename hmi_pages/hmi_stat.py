# hmi_pages/hmi_stat.py
import streamlit as st
import pandas as pd
import plotly.express as px
from data_sys.stat import StatManager

def render_stat_page(symbol_tf_list):
    """
    Аналитическая страница с фильтром по ID (Symbol_TF)
    """
    st.header("📊 Глубокая аналитика портфеля")
    
    # 1. Проверка на пустоту (Guard Clause)
    if not symbol_tf_list:
        st.warning("⚠️ Агенты не настроены. Добавьте валютные пары в настройках.")
        return  # Выход из функции, StatManager не создается
    
    # 2. Инициализация только если есть данные
    stat_mgr = StatManager()

    tab_stats, tab_history = st.tabs(["📈 Метрики и Диаграммы", "📑 Реестр сделок"])

    with tab_stats:
        selected_ids = st.multiselect(
            "Фильтр агентов для агрегации:", 
            symbol_tf_list, 
            default=symbol_tf_list
        )
        
        all_trades = []
        summary_metrics = {"profit": 0, "trades": 0}

        for aid in selected_ids:
            # ВАЖНО: Передаем полный ID (aid) в stat_mgr.get_trades_history
            # В stat.py должна быть реализована фильтрация по этому aid
            df, metrics = stat_mgr.get_trades_history(symbol=aid, days=90)
            
            if not df.empty:
                df['agent_id'] = aid
                df['weekday'] = df.index.day_name()
                all_trades.append(df)
                summary_metrics["profit"] += metrics.get("total_profit_usd", 0)
                summary_metrics["trades"] += metrics.get("total_trades", 0)

        if all_trades:
            combined_df = pd.concat(all_trades)

            # 1. Верхние карточки (KPI)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Общий профит", f"${summary_metrics['profit']:.2f}")
            c2.metric("Всего сделок", summary_metrics['trades'])
            
            win_rate = (len(combined_df[combined_df['profit'] > 0]) / len(combined_df) * 100)
            c3.metric("Win Rate (Avg)", f"{win_rate:.1f}%")
            
            # Profit Factor (защита от деления на ноль, если нет убытков)
            loss_sum = combined_df[combined_df['profit'] <= 0]['profit'].sum()
            profit_factor = abs(combined_df[combined_df['profit'] > 0]['profit'].sum() / (loss_sum if loss_sum != 0 else 0.0001))
            c4.metric("Profit Factor", f"{profit_factor:.2f}")

            st.divider()

            # 2. Графики распределения (Plotly Dark)
            col_a, col_b = st.columns(2)
            
            with col_a:
                fig_day = px.box(combined_df, x="weekday", y="profit", color="agent_id",
                                 title="Распределение прибыли по дням недели",
                                 template="plotly_dark",
                                 category_orders={"weekday": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]})
                st.plotly_chart(fig_day, use_container_width=True)

            with col_b:
                combined_df['hour'] = combined_df.index.hour
                fig_hour = px.bar(combined_df.groupby('hour')['profit'].sum().reset_index(), 
                                  x="hour", y="profit", color_discrete_sequence=px.colors.qualitative.Plotly,
                                  title="Профит по часам (GMT)", template="plotly_dark")
                st.plotly_chart(fig_hour, use_container_width=True)
        else:
            st.info("Нет данных для отображения статистики.")

    with tab_history:
        st.subheader("Реестр закрытых позиций")
        
        target_aid = st.selectbox("Детально по агенту:", ["Все"] + symbol_tf_list)
        
        # Передаем полный ID для фильтрации
        filter_aid = None if target_aid == "Все" else target_aid
        df_history, m = stat_mgr.get_trades_history(filter_aid)
        
        if not df_history.empty:
            if target_aid != "Все":
                st.json(m)
            
            st.dataframe(
                df_history[['symbol', 'type', 'price', 'profit', 'comment']].sort_index(ascending=False),
                use_container_width=True,
                column_config={
                    "profit": st.column_config.NumberColumn("Profit ($)", format="$ %.2f"),
                    "price": st.column_config.NumberColumn("Execution Price", format="%.5f")
                }
            )
        else:
            st.warning("История сделок пуста.")

