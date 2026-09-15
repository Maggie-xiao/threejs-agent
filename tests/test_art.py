import unittest
from art_filter import VERSION, classify, rank_daily
from ai_analyzer import fallback_analysis
from enricher import extract_images


class ArtTests(unittest.TestCase):
    def test_image_extraction(self):
        images=extract_images('![Scene](shots/world.png)<img src="https://img.test/logo.svg">', 'https://raw.githubusercontent.com/a/b/HEAD/')
        self.assertEqual(images,['https://raw.githubusercontent.com/a/b/HEAD/shots/world.png'])
    def case(self):
        return {'visual_evidence': [{'status': 'checked'}], 'analysis': {
            'criteria_version': VERSION, 'stylization_verdict': '符合',
            'world_relevance': True, 'art_observations': ['概括树冠形成轮廓'],
            'takeaways': ['块面植被组织道路层次'], 'technical_value': True,
            'art_scores': {'fit': 8, 'finish': 8, 'takeaway': 8}}}

    def test_gates(self):
        x=self.case(); self.assertEqual(classify(x)['selection_status'],'美术精选')
        x['analysis']['stylization_verdict']='不符合'
        self.assertEqual(classify(x)['selection_status'],'技术备查')
        x['visual_evidence']=[]
        self.assertEqual(classify(x)['selection_status'],'待验证')

    def test_cap(self):
        rows=rank_daily([self.case() for _ in range(30)])
        self.assertEqual(sum(x['selection_status']=='美术精选' for x in rows),20)

    def test_fallback_and_history(self):
        self.assertEqual(classify({'analysis': fallback_analysis({})})['selection_status'],'待验证')
        self.assertEqual(classify({})['selection_status'],'旧规则／未评估')

    def test_low_quality(self):
        x=self.case();x['analysis']['art_scores']['finish']=1
        self.assertNotEqual(classify(x)['selection_status'],'美术精选')
