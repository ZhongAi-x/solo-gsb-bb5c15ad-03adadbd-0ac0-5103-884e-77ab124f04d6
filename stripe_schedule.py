"""条纹用线排程：把总行数切成连续异色条纹段，使各段尽量贴近偏好段长。

模型（段长与代价均为整数，全程精确计算）：
  给定总行数 R、2~3 种颜色（按输入顺序编号 0..n−1，每种颜色有可编织
  行数即库存 q_c）与段长区间 [min_len, max_len]（1~6）。求连续条纹段
  序列 ((c_1, l_1), …, (c_k, l_k))，满足：
    1. 恰好覆盖总行数：Σ l_i = R；
    2. 每段长度在区间内：min_len ≤ l_i ≤ max_len；
    3. 相邻段异色：c_i ≠ c_{i+1}；
    4. 各色用量不超库存：Σ_{i: c_i=c} l_i ≤ q_c。
  在可行方案中最小化 Σ |l_i − preferred|（各段长度与偏好段长的绝对差
  之和）；同分按 (c_i, l_i) 序列字典序最小选择，即逐段先按颜色输入顺序
  （编号小者优先）、同色按段长升序。

求解用分层动态规划：state = (末段颜色 prev（首段前为 -1）, 各色已用量
元组 used)，已用行数由 Σused 决定；每个状态保留到达它的 (代价, 段序列)
中最小的一对——代价第一优先、段序列字典序（即同分比较依据）第二优先。
按已用行数 r = 0 → R 逐层处理：层内每个状态追加一段（颜色不同于末段、
段长在区间内、不超该色库存与剩余行数），落入更大的 r 层。每条边都严格
增加 r，故处理到第 r 层时其所有前驱（更小的 r）均已处理完毕，层内状态
的值已是最优，每个状态恰好扩展一次；取 R 层中 (代价, 段序列) 最小者即
全局最优。
"""

MAX_ROWS = 40
MIN_SEGMENT_LEN = 1
MAX_SEGMENT_LEN = 6


def solve_stripe_schedule(total_rows, colors, min_len, max_len, preferred):
    """求解条纹用线排程。

    参数（调用方已完成校验）：
      total_rows 总行数，int，1 ≤ total_rows ≤ 40
      colors     颜色列表 [{"name", "stock"}]，2~3 个，名称互不相同，
                 stock 为可编织行数（正整数）；下标即颜色输入顺序
      min_len    最短条纹行数，int，1 ≤ min_len ≤ 6
      max_len    最长条纹行数，int，1 ≤ min_len ≤ max_len ≤ 6
      preferred  偏好段长，int，≥ 1（通常取 min_len~max_len）

    可行时返回：
      {"ok": True, "total_rows", "min_len", "max_len", "preferred",
       "colors": [{"index", "name", "stock", "used", "remaining"}, ...],
       "segments": [{"index", "color_index", "color", "length",
                     "start_row", "end_row"}, ...],
       "num_segments", "cost"}
      各段 start_row/end_row 从 1 计且首尾相接，end_row 恰为 total_rows；
      colors 中的 used/remaining 为各色实际用量与余量（stock − used）。
    无解时返回：
      {"ok": False, "reason"}
      reason ∈ {"insufficient_stock", "infeasible"}：
      库存合计少于总行数时为 insufficient_stock，其余满足约束的段切分
      不存在（如段长区间无法恰好凑成总行数、必须同色相邻、各色库存不足
      以承担所需段数）时为 infeasible。无解时不返回任何部分安排。
    """
    n = len(colors)
    stocks = tuple(c["stock"] for c in colors)

    infeasible = {"ok": False, "total_rows": total_rows,
                  "min_len": min_len, "max_len": max_len,
                  "preferred": preferred}
    if sum(stocks) < total_rows:
        # 所有颜色的可编织行数合计都不够，任何切分都无法覆盖总行数
        return dict(infeasible, reason="insufficient_stock")

    zero_used = (0,) * n
    # layers[r]：已用恰好 r 行的一层，state (prev, used) -> (cost, segments)。
    # 同状态保留 (代价, 段序列) 最小的前缀：从同一状态出发的未来代价只与
    # 状态有关，与到达路径无关；段序列字典序正是同分比较依据。
    layers = [None] * (total_rows + 1)
    layers[0] = {(-1, zero_used): (0, ())}
    for used_rows in range(total_rows):
        current = layers[used_rows]
        if not current:
            continue  # 该行数没有可行前缀；更大的层数可能仍由别的层到达
        remaining_rows = total_rows - used_rows
        for (prev, used), (cost, segments) in current.items():
            for color in range(n):
                if color == prev:
                    continue  # 相邻段必须异色
                room = min(stocks[color] - used[color], max_len)
                if room < min_len:
                    continue  # 库存不足一段，或剩余可用量小于最短段长
                upper = min(room, remaining_rows)
                for length in range(min_len, upper + 1):
                    new_used_list = list(used)
                    new_used_list[color] += length
                    new_used = tuple(new_used_list)
                    new_state = (color, new_used)
                    new_value = (cost + abs(length - preferred),
                                 segments + ((color, length),))
                    target = layers[used_rows + length]
                    if target is None:
                        target = {}
                        layers[used_rows + length] = target
                    old = target.get(new_state)
                    if old is None or new_value < old:
                        target[new_state] = new_value

    final = layers[total_rows]
    if not final:
        return dict(infeasible, reason="infeasible")

    # final 中各方案都恰好覆盖 total_rows 行，取 (代价, 段序列) 最小者：
    # 先最小化绝对差之和，同分逐段按颜色输入顺序、再按段长升序
    _state, (best_cost, best_segments) = min(
        final.items(), key=lambda item: item[1])

    plan_segments = []
    totals = [0] * n
    row_cursor = 0
    for index, (color, length) in enumerate(best_segments, 1):
        totals[color] += length
        plan_segments.append({
            "index": index,
            "color_index": color,
            "color": colors[color]["name"],
            "length": length,
            "start_row": row_cursor + 1,
            "end_row": row_cursor + length,
        })
        row_cursor += length

    return {
        "ok": True,
        "total_rows": total_rows,
        "min_len": min_len,
        "max_len": max_len,
        "preferred": preferred,
        "colors": [{
            "index": i,
            "name": colors[i]["name"],
            "stock": stocks[i],
            "used": totals[i],
            "remaining": stocks[i] - totals[i],
        } for i in range(n)],
        "segments": plan_segments,
        "num_segments": len(plan_segments),
        "cost": best_cost,
    }
