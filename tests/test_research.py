import unittest
from copy import deepcopy
from volatility_lab.core import analyze
from volatility_lab.data import demo
from volatility_lab.research import evaluate

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.raw=demo()
        self.rows=[r for r in analyze(self.raw['rows'],100,.04,.01) if r['kind']=='call']
    def run_eval(self,rows):
        return evaluate(rows,100,.04,.01)
    def test_deterministic_and_baseline_comparison(self):
        a=self.run_eval(self.rows)
        self.assertEqual(a,self.run_eval(self.rows))
        self.assertGreater(a['test_quotes'],0)
        self.assertLess(a['summary'][2]['price_mae'],a['summary'][0]['price_mae'])
    def test_held_out_targets_do_not_change_predictions(self):
        a=self.run_eval(self.rows)
        held={(p['strike'],p['days']) for p in a['predictions']}
        changed=deepcopy(self.rows)
        for r in changed:
            if (r['strike'],r['days']) in held:
                r['iv']+=.2
                r['mid']+=1
        b=self.run_eval(changed)
        self.assertEqual([p['predicted_price'] for p in a['predictions']],
                         [p['predicted_price'] for p in b['predictions']])
    def test_too_few_strikes(self):
        with self.assertRaises(ValueError): self.run_eval(self.rows[:3])
