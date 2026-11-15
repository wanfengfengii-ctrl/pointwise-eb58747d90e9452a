# 血缘影响闭包的既有接口

本仓库把表之间的直接依赖落在 SQLite 的 edge 中，把非空路径可达关系物化在 reach 中。src→dst 表示 src 的变化可能影响 dst。store.py 提供持久化与双向范围索引，closure.py 传播关系变化，warehouse.py 管理批次事务；checks.py 的全量遍历仅是核账参照，不是生产实现。

## 调用与输入输出

使用 Python 标准库。公开入口为：

    from warehouse import Warehouse
    w = Warehouse()                 # 默认使用内存数据库
    w = Warehouse("lineage.sqlite")  # 也可创建或打开持久数据库
    w.apply(add=[("a", "b")], remove=[])
    assert w.reachable() == [("a", "b")]
    assert w.edges() == [("a", "b")]
    w.close()

apply(add=(), remove=()) 返回 None。add、remove 是边的可迭代集合；每条边为长度 2 的列表或元组，两个端点都是非空字符串。集合内重复边去重。两集合交叠、端点为空或非字符串、边长度错误均抛 ValueError，源边和闭包不变。重复新增已有边、删除不存在边均无副作用。

每批以最终边集 (旧边集 - remove) ∪ add 原子生效，外部不能看到半批结果。reachable() 返回按 (src,dst) 排序的元组列表，且每对只出现一次。edges() 同样返回排序后的源边列表。闭包表示至少一条非空有向路径，不把长度零当路径；自环合法，自身可达仅在存在环时成立。允许多个替代路径，删除一路不能删掉仍有路径的结果。

例如源边 a→b、b→a、b→c，删除 a→b 后应只剩可达关系 b→a、b→c。samples.py 是另一宗封存事故：删除 raw→stage 后，stage 与 quality 的循环仍在，但 raw 不应再可达任何表；EXPECTED_AFTER 给出完整排序结果。

## 局部维护与计量

修复必须继续利用已有闭包及双向索引。不得每批清空重建、逐源重新遍历全部可达子图、全量重放历史，或扫描无关连通部分。某源的一条依赖受影响，不代表可以重走该源所有稳定分支。允许访问变更边关联的前驱、传播涉及的待撤回关系，以及判断这些关系仍否有支持所需的局部索引范围。可以调整内部维护状态，但不能用核账参照替代生产链路。

Warehouse.metrics 固定记录最近一次 apply 的维护读取，不含调用方随后执行 edges/reachable 的展示成本：
- point_probes：精确键查询次数，无论命中与否。
- range_calls：索引范围查询次数，包括空范围。
- index_rows：范围查询实际返回的行数。
- full_scans：无范围限定的源边或闭包枚举次数。

保留 store.py 的读取计量；新增或改写维护查询也须按同一口径计入，不得绕过或虚报。公开局部性样例中，每次撤销的 point_probes + range_calls + index_rows 不超过 100，full_scans 为 0。样例包含同一受影响源的 200/2000 条稳定分支和独立的 60 边链，防止以重算源或扫描全库替代局部撤回。这里不要求并发处理、崩溃恢复、规则扩展或旧库格式迁移。

## 已有回归、事故和交付

下面的命令均从仓库根目录运行：

    python3 checks.py regression
    python3 checks.py reproduce
    python3 checks.py verify
    python3 checks.py demo

regression 核账菱形替代路径、同批替换、重复操作、非法批次和一类环断边，并核对无环局部撤销计量；原基线应通过。reproduce 独立创建事故源边，验证初态后撤销入口；错误残留时以 LINEAGE_CYCLE_RETRACTION 标记失败。修复后该命令须成功并核对 EXPECTED_AFTER。

verify 依次执行原回归、事故、固定种子小图逐批全量参照及带环局部性核验；全部断言须通过。demo 输出事故的真实源边、撤销前后闭包、期望结果及本次维护计量，不用写死的成功文案替代结果。reference 只读测试维护的源边集合，不调用生产闭包推导方法。

保留原业务断言与样例，可补充必要回归。交付修复代码和简短说明，解释根因、修复后的维护不变量，并记录实际执行的验证结果。.pointwise-runtime.json 已登记核验和演示的 argv；保留这两个可执行入口，准备步骤仍为空列表。
