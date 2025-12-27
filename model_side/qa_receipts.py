# Copyright 2025  Tarik En Nakhai
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import json, sys, math
path = sys.argv[1]
bad_sum = bad_order = bad_neg = 0
with open(path, "r", encoding="utf-8") as f:
    for ln, line in enumerate(f, 1):
        if not line.strip(): continue
        o = json.loads(line)
        if o.get("schema")!="royalty_receipt.v1": continue
        tk = o.get("top_k") or []
        # somma
        s = sum(float(x.get("share",0)) for x in tk)
        if not (0.99 <= s <= 1.01):
            bad_sum += 1
        # non-negativi
        if any((x.get("share",0) < 0) for x in tk):
            bad_neg += 1
        # ordinamento per rank
        ranks = [x.get("rank") for x in tk if isinstance(x.get("rank"), int)]
        if ranks and ranks != sorted(ranks):
            bad_order += 1
print(f"[QA] bad_sum={bad_sum}  bad_neg={bad_neg}  bad_order={bad_order}")

