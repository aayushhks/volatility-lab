import unittest
from math import exp,nan
from volatility_lab.core import price,vega,implied_vol,analyze
from volatility_lab.data import demo
class PricingTests(unittest.TestCase):
    def test_reference_price(self):
        self.assertAlmostEqual(price(100,100,1,.05,.2),10.450583572,places=7)
        self.assertAlmostEqual(price(100,100,1,.05,.2,kind='put'),5.573526022,places=7)
    def test_put_call_parity(self):
        for t in (.1,1,2):
            for k in (80,100,120):
                self.assertAlmostEqual(price(100,k,t,.04,.3,.02)-price(100,k,t,.04,.3,.02,'put'),100*exp(-.02*t)-k*exp(-.04*t),places=10)
    def test_iv_round_trip(self):
        for kind in ('call','put'):
            for vol in (.15,.3,.8):
                for k in (90,100,110):
                    p=price(100,k,.5,.03,vol,.01,kind)
                    self.assertAlmostEqual(implied_vol(p,100,k,.5,.03,.01,kind),vol,places=7)
    def test_vega_finite_difference(self):
        h=1e-5
        d=(price(100,105,.7,.02,.3+h,.01)-price(100,105,.7,.02,.3-h,.01))/(2*h)
        self.assertAlmostEqual(vega(100,105,.7,.02,.3,.01),d,places=6)
    def test_bounds_reject(self):
        for p in (-1,0,100,101,nan):
            with self.assertRaises(ValueError): implied_vol(p,100,100,1,.05)
    def test_bad_inputs(self):
        for s,k,t in [(0,100,1),(100,-1,1),(100,100,0),(nan,100,1)]:
            with self.assertRaises(ValueError): price(s,k,t,.02,.2)
    def test_quality_filters(self):
        rows=[dict(strike=100,days=30,bid=b,ask=a,kind='call') for b,a in [(4,3),(0,2),(1,10),(nan,4)]]
        self.assertTrue(all(x['status']=='rejected' for x in analyze(rows,100,.04,.01)))
    def test_fixture_recovery(self):
        for name in ('Balanced','Steep skew','Short-term stress'):
            d=demo(name); results=analyze(d['rows'],d['spot'],d['rate'],d['yield_rate'])
            good=[x for x in results if x['status']=='accepted']
            self.assertGreater(len(good),100)
            for x in good:
                self.assertLess(x['repricing_error'],1.1e-8)
                self.assertAlmostEqual(x['iv'],x['known_iv'],places=5)
    def test_vol_monotonicity(self):
        self.assertLess(price(100,100,1,.02,.2),price(100,100,1,.02,.3))
    def test_zero_vol(self):
        self.assertAlmostEqual(price(100,100,1,.05,0),100-100*exp(-.05))
if __name__=='__main__': unittest.main()
