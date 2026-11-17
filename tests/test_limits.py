import unittest
from volatility_lab.limits import check_upload_size,check_surface_size,MAX_UPLOAD_BYTES
class MemoryLimitTests(unittest.TestCase):
    def test_upload_rejected_before_parse(self):
        with self.assertRaises(ValueError): check_upload_size(MAX_UPLOAD_BYTES+1)
        check_upload_size(MAX_UPLOAD_BYTES)
    def test_sparse_input_cannot_explode_to_dense_grid(self):
        with self.assertRaises(ValueError): check_surface_size(20000,20000)
        check_surface_size(1000,100)
