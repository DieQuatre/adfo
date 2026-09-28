"""
ui/pages/3_Dynamic_Relocation.py
=================================
Dynamic storage relocation (Kübler §5.3 / §6.4) — uses run_dynamic.run_experiment.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
from core.dynamic_data import from_generated, from_kubler
from run_dynamic import ALGOS, run_experiment

st.set_page_config(page_title="Dynamic Relocation", page_icon="🔄", layout="wide")
st.title("🔄 Dynamic Storage Relocation")
st.markdown(
    "Each test period is solved twice with the same orders: **static** (items stay where they "
    "started) and **dynamic** (relocations accepted at the end of earlier periods are applied). "
    "At the end of each period, Holt-Winters forecasts demand, items stored in the wrong class "
    "are ranked, and relocation suggestions are accepted when the estimated future travel-distance "
    "reduction exceeds the relocation effort."
)

with st.sidebar:
    st.header("⚙️ Parameters")
    source = st.radio("Data", ["Kübler data set", "Generated warehouse"])
    if source == "Kübler data set":
        scenario = st.selectbox("Scenario", [1, 2],
                                format_func=lambda x: f"Scenario {x} ({'high' if x == 1 else 'low'} dynamics)")
    else:
        size = st.selectbox("Locations (target)", config.GENERATOR['grid_sizes'])
        blocks = st.selectbox("Blocks", config.GENERATOR['grid_blocks'])
        fill = st.selectbox("Fill rate", config.GENERATOR['grid_fills'])
        dyn = st.selectbox("Dynamics", list(config.GENERATOR['dynamics']), index=2)
    algo = st.radio("Batching algorithm", ALGOS, index=3,
                    help="FIRSTFIT is a fast baseline for exploration; the paper uses DEPSO.")
    used = st.slider("Sub-periods solved per period (of 20)", 1, 20, 4)
    n_periods = st.slider("Test periods", 2, 9, 9)
    d_iter = st.slider("DEPSO iterations", 20, 500, 100)
    st.caption(f"o = {config.DYNAMIC_STORAGE['min_periods_in_wrong_class_o']}, "
               f"u = {config.DYNAMIC_STORAGE['min_periods_in_target_class_u']}, "
               f"max. suggestions = {config.DYNAMIC_STORAGE['max_relocation_suggestions']}, "
               f"forecast horizon = {config.DYNAMIC_STORAGE['forecast_horizon']}")


@st.cache_resource
def problem_for(key):
    if key[0] == 'kubler':
        return from_kubler(key[1])
    from core.generator import InstanceSpec, generate
    return from_generated(generate(InstanceSpec(*key[1:])))


if st.button("🚀 Run", type="primary", use_container_width=True):
    key = ('kubler', scenario) if source == "Kübler data set" else ('gen', size, blocks, fill, dyn, 0)
    problem = problem_for(key)
    box = st.empty()
    progress_rows = []

    def show(row):
        progress_rows.append(row)
        box.dataframe(pd.DataFrame(progress_rows)[['period', 'td_static', 'td_dynamic',
                                                   'reduction_pct', 'effort_pct', 'net_pct',
                                                   'accepted', 'tested']],
                      use_container_width=True)

    with st.spinner("Running…"):
        rows, summary = run_experiment(problem, algo, d_iter, used, n_periods, progress=show)

    c1, c2, c3 = st.columns(3)
    c1.metric("Travel distance reduction", f"{summary['reduction_pct']:.2f}%")
    c2.metric("Relocation effort", f"{summary['effort_pct']:.2f}%")
    c3.metric("Net improvement", f"{summary['net_pct']:.2f}%")
    if key[0] == 'kubler':
        t = config.VALIDATION_TARGETS
        st.caption(f"Paper (scenario {scenario}, DEPSO, full periods): reduction "
                   f"{t[f'scenario{scenario}_travel_distance_reduction_pct']}%, effort "
                   f"{t[f'scenario{scenario}_relocation_effort_pct']}%, net "
                   f"{t[f'scenario{scenario}_net_improvement_pct']}%. See docs/RELOCATION.md "
                   f"for why the reconstructed data set gives smaller reductions.")

    fig = go.Figure()
    fig.add_bar(x=[r['period'] for r in rows], y=[r['reduction_pct'] for r in rows],
                name="Travel distance reduction %")
    fig.add_bar(x=[r['period'] for r in rows], y=[r['effort_pct'] for r in rows],
                name="Relocation effort %")
    fig.update_layout(barmode='group', xaxis_title="Test period", yaxis_title="% of static distance",
                      height=380, plot_bgcolor="white")
    st.plotly_chart(fig, use_container_width=True)
