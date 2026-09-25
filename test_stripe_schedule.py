import random
import unittest

from stripe_schedule import solve_stripe_schedule


def brute_force(total_rows, colors, min_len, max_len, preferred):
    """暴力枚举所有满足约束的段序列，返回 (最小代价, 段序列) 或 None。

    段序列编码为 ((颜色编号, 段长), ...)；同分按其字典序取最小，
    即逐段先按颜色输入顺序（编号升序）、再按段长升序。
    """
    n = len(colors)
    stocks = tuple(c['stock'] for c in colors)

    def extend(pos, prev, used, segments):
        if pos == total_rows:
            cost = sum(abs(length - preferred) for _c, length in segments)
            return cost, tuple(segments)
        best = None
        remaining = total_rows - pos
        for color in range(n):
            if color == prev:
                continue
            upper = min(max_len, stocks[color] - used[color], remaining)
            for length in range(min_len, upper + 1):
                new_used = list(used)
                new_used[color] += length
                candidate = extend(
                    pos + length, color, tuple(new_used),
                    segments + [(color, length)])
                if candidate is not None and (best is None or candidate < best):
                    best = candidate
        return best

    return extend(0, -1, (0,) * n, [])


def segment_tuple(result):
    """从求解结果取出 ((颜色编号, 段长), ...)。"""
    return tuple((s['color_index'], s['length']) for s in result['segments'])


class TestSolveStripeSchedule(unittest.TestCase):
    def test_example_three_colors(self):
        # 文档示例：12 行，红6 蓝5 绿3，段长 2~6，偏好 4。
        # 4+5+3（红/蓝/绿）代价 0+1+1=2；库存全在界内
        result = solve_stripe_schedule(
            12, [{'name': '红', 'stock': 6}, {'name': '蓝', 'stock': 5},
                 {'name': '绿', 'stock': 3}], 2, 6, 4)
        self.assertTrue(result['ok'])
        self.assertEqual(segment_tuple(result), ((0, 4), (1, 5), (2, 3)))
        self.assertEqual(result['cost'], 2)
        self.assertEqual(result['num_segments'], 3)
        self.assertEqual(
            [(s['start_row'], s['end_row']) for s in result['segments']],
            [(1, 4), (5, 9), (10, 12)])
        self.assertEqual([(c['name'], c['used'], c['remaining'])
                          for c in result['colors']],
                         [('红', 4, 2), ('蓝', 5, 0), ('绿', 3, 0)])

    def test_single_segment_covers_all_rows(self):
        # 4 行可由颜色 0 一段覆盖：代价 |4-4|=0，无需异色
        result = solve_stripe_schedule(
            4, [{'name': 'A', 'stock': 10}, {'name': 'B', 'stock': 10}],
            1, 6, 4)
        self.assertTrue(result['ok'])
        self.assertEqual(segment_tuple(result), ((0, 4),))
        self.assertEqual(result['cost'], 0)

    def test_tie_breaks_by_color_input_order(self):
        # 6 行、两色库存各 6、段长 2~6、偏好 3：3+3 代价 0，
        # A/B 或 B/A 均可，取颜色输入顺序在前的 A 开头
        result = solve_stripe_schedule(
            6, [{'name': 'A', 'stock': 6}, {'name': 'B', 'stock': 6}],
            2, 6, 3)
        self.assertTrue(result['ok'])
        self.assertEqual(segment_tuple(result), ((0, 3), (1, 3)))
        self.assertEqual(result['cost'], 0)

        # 交换颜色输入顺序后首段应换为新的第一色
        swapped = solve_stripe_schedule(
            6, [{'name': 'B', 'stock': 6}, {'name': 'A', 'stock': 6}],
            2, 6, 3)
        self.assertEqual(segment_tuple(swapped), ((0, 3), (1, 3)))
        self.assertEqual(swapped['segments'][0]['color'], 'B')

    def test_tie_breaks_by_segment_length_ascending(self):
        # 8 行、两色库存各 8、段长 1~6、偏好 3：
        # A-B-A 下 2+3+3 与 3+2+3 代价同为 1，首段段长升序取 2
        result = solve_stripe_schedule(
            8, [{'name': 'A', 'stock': 8}, {'name': 'B', 'stock': 8}],
            1, 6, 3)
        self.assertTrue(result['ok'])
        self.assertEqual(segment_tuple(result),
                         ((0, 2), (1, 3), (0, 3)))
        self.assertEqual(result['cost'], 1)

    def test_preference_cost_zero_prefers_exact_lengths(self):
        # 40 行、3 色大库存、段长 1~6、偏好 4：十段 4 行代价 0
        result = solve_stripe_schedule(
            40, [{'name': 'A', 'stock': 40}, {'name': 'B', 'stock': 40},
                 {'name': 'C', 'stock': 40}], 1, 6, 4)
        self.assertTrue(result['ok'])
        self.assertEqual(result['cost'], 0)
        self.assertTrue(all(s['length'] == 4 for s in result['segments']))
        self.assertEqual(result['num_segments'], 10)
        # 相邻段异色
        colors_used = [s['color_index'] for s in result['segments']]
        self.assertTrue(all(colors_used[i] != colors_used[i + 1]
                            for i in range(len(colors_used) - 1)))

    def test_segments_cover_exactly_and_stock_respected(self):
        result = solve_stripe_schedule(
            30, [{'name': 'A', 'stock': 10}, {'name': 'B', 'stock': 20}],
            2, 5, 3)
        self.assertTrue(result['ok'])
        self.assertEqual(result['segments'][0]['start_row'], 1)
        self.assertEqual(result['segments'][-1]['end_row'], 30)
        for prev, seg in zip(result['segments'], result['segments'][1:]):
            self.assertEqual(prev['end_row'] + 1, seg['start_row'])
            self.assertNotEqual(prev['color_index'], seg['color_index'])
        for color in result['colors']:
            self.assertLessEqual(color['used'], color['stock'])
            self.assertEqual(color['remaining'], color['stock'] - color['used'])

    def test_infeasible_min_len_too_large(self):
        # 1 行、最短 2：任何一段都至少 2 行，无法覆盖
        result = solve_stripe_schedule(
            1, [{'name': 'A', 'stock': 10}, {'name': 'B', 'stock': 10}],
            2, 6, 2)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'infeasible')

    def test_infeasible_total_not_representable(self):
        # 7 行、段长只能为 2：两段最多 4 行、三段最少 6 行但 3×2=6≠7，
        # 且四段最少 8 行——无法恰好凑出 7
        result = solve_stripe_schedule(
            7, [{'name': 'A', 'stock': 10}, {'name': 'B', 'stock': 10}],
            2, 2, 2)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'infeasible')

    def test_infeasible_stock_shortage_total(self):
        # 库存合计 4 < 总行数 5
        result = solve_stripe_schedule(
            5, [{'name': 'A', 'stock': 2}, {'name': 'B', 'stock': 2}],
            1, 6, 3)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'insufficient_stock')

    def test_infeasible_color_cannot_fill_even_one_segment(self):
        # 库存合计够，但颜色 A 只有 1 行、最短 2 行：A 无法成段，
        # 只剩 B 一色而相邻段必须异色，B 无法独自覆盖 7 行（最多一段）
        result = solve_stripe_schedule(
            7, [{'name': 'A', 'stock': 1}, {'name': 'B', 'stock': 10}],
            2, 6, 3)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'infeasible')

    def test_stock_structural_constraint_binds(self):
        # 10 行、A 库存 2、B 库存 8、段长 3~4：B 虽多但必须被 A 段隔开，
        # A 只够一段（3 行库存都不够），故无解
        result = solve_stripe_schedule(
            10, [{'name': 'A', 'stock': 2}, {'name': 'B', 'stock': 8}],
            3, 4, 3)
        self.assertFalse(result['ok'])
        self.assertEqual(result['reason'], 'infeasible')

    def test_random_against_brute_force(self):
        # 随机小参数与暴力枚举对照：代价与段序列都必须一致
        rng = random.Random(20260925)
        for _ in range(200):
            total_rows = rng.randint(1, 10)
            n = rng.randint(2, 3)
            names = ['A', 'B', 'C'][:n]
            colors = [{'name': names[i], 'stock': rng.randint(1, total_rows + 2)}
                      for i in range(n)]
            min_len = rng.randint(1, 4)
            max_len = rng.randint(min_len, 6)
            preferred = rng.randint(1, 6)
            result = solve_stripe_schedule(
                total_rows, colors, min_len, max_len, preferred)
            best = brute_force(total_rows, colors, min_len, max_len, preferred)
            msg = ('参数 rows={} colors={} len={}~{} pref={}'.format(
                total_rows, colors, min_len, max_len, preferred))
            if best is None:
                self.assertFalse(result['ok'], msg=msg)
            else:
                self.assertTrue(result['ok'], msg=msg)
                self.assertEqual(result['cost'], best[0], msg=msg)
                self.assertEqual(segment_tuple(result), best[1], msg=msg)


if __name__ == '__main__':
    unittest.main()
