"""Research panel, available even when the quote provider is unavailable."""
import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from .core import analyze
from .data import demo
from .research import evaluate


def render(raw, rate, q, spread, oi, kind):
    with st.expander('Research experiment · predict held-out option prices', expanded=raw is None):
        st.write('Can a smile interpolation estimate unseen option quotes better than constant volatility?')
        choices=['Offline synthetic benchmark']
        if raw is not None: choices.append('Current snapshot')
        source=st.selectbox('Experiment dataset',choices)
        if source=='Offline synthetic benchmark':
            scenario=st.selectbox('Benchmark scenario',['Balanced','Steep skew','Short-term stress'])
            dataset=demo(scenario)
            r,y=dataset['rate'],dataset['yield_rate']
            st.info('Generated European option prices, not market observations. This tests interpolation on a known smooth smile; it does not establish trading performance.')
        else:
            dataset=raw
            r,y=rate,q
            st.caption('Uses the current snapshot and sidebar filters. This is cross-sectional interpolation, not future price prediction.')
        seed=st.number_input('Holdout seed',min_value=0,max_value=100000,value=42)
        accepted=[row for row in analyze(dataset['rows'],dataset['spot'],r,y,spread,oi) if row.get('kind')==kind]
        try: result=evaluate(accepted,dataset['spot'],r,y,int(seed))
        except ValueError as exc:
            st.info(str(exc)); return
        st.caption(f"Training: {result['train_quotes']} quotes · held out: {result['test_quotes']} · skipped: {result['skipped_quotes']}")
        table=pd.DataFrame(result['summary']).rename(columns={'method':'Method','test_quotes':'Test quotes','price_mae':'Price MAE ($)','price_rmse':'Price RMSE ($)','iv_mae_bp':'IV MAE (bp)','within_spread_pct':'Inside bid/ask (%)'})
        st.dataframe(table,hide_index=True,width='stretch')
        fig=go.Figure(go.Bar(x=[m['method'] for m in result['summary']],y=[m['price_mae'] for m in result['summary']],marker_color=['#172554','#0e7490','#b45309']))
        fig.update_layout(yaxis_title='Held-out price MAE ($ per share)',height=300)
        st.plotly_chart(fig,width='stretch')
        st.markdown('**Protocol:** hold out approximately 20% of distinct interior strikes in each expiry; keep boundary strikes in training. Duplicate strikes stay together. All three methods use the same training/test split. Expiries with fewer than five strikes are excluded. No extrapolation is evaluated.')
        st.caption('Results depend on the split and quote filters. Try multiple seeds. Inside-bid/ask agreement is not profit, and these methods impose no arbitrage constraints. Synthetic generation and evaluation share the same pricing model.')
        report=dict(dataset=dataset,assumptions=dict(rate=r,yield_rate=y,max_spread=spread,min_oi=oi,kind=kind),evaluation=result)
        st.download_button('Download experiment and source snapshot',json.dumps(report,indent=2,default=str),'holdout-experiment.json','application/json')
        st.download_button('Download held-out predictions',pd.DataFrame(result['predictions']).to_csv(index=False),'heldout-predictions.csv','text/csv')
