import json
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from volatility_lab.core import analyze
from volatility_lab.data import demo,fetch_yahoo

st.set_page_config(page_title='Volatility Lab',page_icon='〰',layout='wide')
st.title('Volatility Lab')
st.caption('From option quotes to implied volatility. Explore the surface, inspect the data, understand the assumptions.')
with st.sidebar:
    st.header('Research controls')
    mode=st.radio('Data source',['Synthetic demo','Yahoo Finance','CSV upload'])
    scenario=st.selectbox('Demo scenario',['Balanced','Steep skew','Short-term stress']) if mode=='Synthetic demo' else 'Balanced'
    rate=st.number_input('Risk-free rate (%)',-10.,30.,4.,.25)/100
    q=st.number_input('Continuous dividend yield (%)',0.,30.,1.,.25)/100
    spread=st.slider('Maximum bid/ask spread (% of mid)',5,100,30)/100
    oi=st.number_input('Minimum open interest',0,100000,0)
    kind=st.selectbox('Option side',['call','put'])
    raw=None
    if mode=='Synthetic demo': raw=demo(scenario)
    elif mode=='Yahoo Finance':
        symbol=st.text_input('Ticker','SPY').strip().upper()
        n=st.slider('Maximum expiries to request',1,12,6)
        if st.button('Fetch option chains',type='primary'):
            try:
                with st.spinner('Requesting option chains…'):
                    st.session_state['market']=fetch_yahoo(symbol,n)
            except Exception as exc: st.error(f'Live fetch failed: {exc}. Try CSV or the synthetic demo.')
        raw=st.session_state.get('market')
        if raw and raw['symbol']!=symbol: st.info('Displayed snapshot is for '+raw['symbol']+'. Fetch to change it.')
    else:
        upload=st.file_uploader('Quotes CSV',type='csv')
        st.caption('Required: strike, days, bid, ask, kind. Optional: open_interest. days = time remaining at observation.')
        spot=st.number_input('Underlying spot',min_value=.01,value=100.)
        if upload:
            try:
                frame=pd.read_csv(upload)
                missing=set(['strike','days','bid','ask','kind'])-set(frame.columns)
                if missing: st.error('Missing columns: '+', '.join(sorted(missing)))
                elif frame.empty: st.error('The CSV contains no quote rows.')
                elif len(frame)>20000: st.error('Limit: 20,000 quote rows.')
                else: raw=dict(symbol='CSV',spot=spot,rows=frame.to_dict('records'),source='User-provided CSV')
            except Exception as exc: st.error('Cannot parse CSV: '+str(exc))

if raw is None:
    st.info('Fetch a ticker or upload a CSV to begin. Synthetic demo works without network access.')
    st.stop()
st.subheader(raw['symbol']+' · '+raw['source'])
if mode=='Synthetic demo': st.info('Synthetic prices generated with a known volatility smile. Changing rate/yield re-inverts these fixed quotes using your new assumptions.')
else: st.warning('European-model implied volatility. US equity/ETF options may allow early exercise. Spot and quotes may be delayed or asynchronous; this is not a live trading feed.')
if raw.get('fetched_at'): st.caption(f"Fetched {raw['fetched_at']} · underlying bar {raw['spot_timestamp']}")
for error in raw.get('errors',[]): st.warning('Partial fetch: '+error)
all_rows=analyze(raw['rows'],raw['spot'],rate,q,spread,oi)
audit=pd.DataFrame(all_rows)
good=audit[(audit.status=='accepted') & (audit.kind==kind)].copy()
a,b,c,d=st.columns(4)
a.metric('Underlying spot',f"${raw['spot']:.2f}")
b.metric('Accepted quotes',int((audit.status=='accepted').sum()))
c.metric('Rejected quotes',int((audit.status=='rejected').sum()))
d.metric('Max repricing error',f"${audit.loc[audit.status=='accepted','repricing_error'].max():.2g}" if (audit.status=='accepted').any() else '—')
if good.empty:
    st.warning('No quotes passed these filters. Inspect the audit below or adjust the assumptions.')
else:
    x=sorted(good.moneyness.unique()); y=sorted(good.days.unique())
    grid=good.pivot_table(index='days',columns='moneyness',values='iv',aggfunc='median').reindex(index=y,columns=x)*100
    fig=go.Figure(go.Surface(x=x,y=y,z=grid.values,colorscale='Teal',connectgaps=False,colorbar_title='IV %'))
    fig.update_layout(height=570,margin=dict(l=0,r=0,t=10,b=0),scene=dict(xaxis_title='Strike / spot',yaxis_title='Days to expiry',zaxis_title='IV (%)'))
    st.plotly_chart(fig,width='stretch')
    st.caption('Surface connects adjacent valid grid points for display only; missing quotes remain gaps. Not an arbitrage-free calibrated surface.')
    left,right=st.columns(2)
    with left:
        expiry=st.selectbox('Smile slice: days to expiry',y)
        sl=good[good.days==expiry].sort_values('moneyness')
        st.plotly_chart(go.Figure(go.Scatter(x=sl.moneyness,y=sl.iv*100,mode='lines+markers')).update_layout(xaxis_title='Strike / spot',yaxis_title='IV (%)',height=300),width='stretch')
    with right:
        nearest=good.assign(distance=abs(good.moneyness-1)).sort_values('distance').groupby('days').first().reset_index()
        st.plotly_chart(go.Figure(go.Scatter(x=nearest.days,y=nearest.iv*100,mode='lines+markers')).update_layout(title='Nearest-to-spot term structure',xaxis_title='Days',yaxis_title='IV (%)',height=300),width='stretch')
        st.caption('Each expiry uses its closest available strike, so this is not constant-delta or interpolated ATM volatility.')
with st.expander('Quote audit and exclusions',expanded=True):
    st.dataframe(audit,width='stretch',hide_index=True)
    st.download_button('Download full audit CSV',audit.to_csv(index=False),'volatility-audit.csv','text/csv')
st.download_button('Download reproducible snapshot',json.dumps(dict(data=raw,assumptions=dict(rate=rate,yield_rate=q,max_spread=spread,min_oi=oi)),indent=2,default=str),'snapshot.json','application/json')
with st.expander('Method and limitations'):
    st.markdown('''1. Validate positive, uncrossed bid/ask quotes and apply spread / open-interest filters.
2. Price at the bid/ask midpoint; never substitute an old last trade.
3. Check European price bounds, then solve Black–Scholes–Merton for volatility using bracketed bisection (0–500%).
4. Reprice every accepted quote and record the residual. Use ACT/365 and continuous rate/dividend yield.

The chart is exploratory: no claim of predictive edge, profitability, or arbitrage-free calibration. Quote-age checks are unavailable because Yahoo does not reliably provide bid/ask timestamps. Last-trade timestamps are retained but are not quote timestamps. Deep ITM and near-expiry IV can be numerically unstable. Rates/yields are user assumptions, not a fitted term structure. Discrete dividends and early exercise are not modeled.''')
