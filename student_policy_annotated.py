"""供檢視與講解的 ``student_policy.py`` 中文詳註副本。

這個 ``annotated/`` 目錄內的檔案不會被 runner 執行；修改它也不會改變實驗
結果。實際執行與課堂修改的檔案仍是專案根目錄的 ``student_policy.py``。

以下保留根目錄策略的相同程式邏輯，並用中文逐段說明其作用。

本檔的工作很單純：runner 每隔一個固定 step 提供一次目前狀態，
``choose_action()`` 再回傳一個動作名稱。這裡決定「何時休息、等待或嘗試傳送」，
不是直接控制真實無線電，也不保證每次傳送都成功。

閱讀順序可分成三段：先認識五個合法動作，再看三組可修改常數，最後由上而下
閱讀 ``choose_action()`` 的六個判斷。本課雖允許三個 marked block 內的合法值，
每次實驗仍只做指定替換：Lab A 改 SLEEP → WAIT；Lab B 改 2 → 1；Lab C 依序
改 20 → 5 → 30。沒有被點名的值、註解、判斷順序與函式都保持不變。

本檔只供閱讀，不會被 runner 讀取或執行。正常 run 只執行專案根目錄的
``student_policy.py``；``student_policy.baseline.py`` 是比對與 recovery reference。
runner 會核對根目錄策略的 UTF-8/LF 原始 bytes，建立 identity，再於本機執行。
Leo 網站只接收 runner 產生的 ``result.json``；驗證後建立配對的 endpoint replay，
不接收或執行任何 ``student_policy.py``。

結果依序查看 attempted、delivered、collision、retransmission、expired、deadline、
service_pass、endpoint_energy_j 與 endpoint bit/J。這些都是模擬的端點無線電／
處理能量，不是實測、即時、canonical 或整個衛星系統的能量。
"""

# runner 接受的五種動作。它們是固定的「請求名稱」，不可自行改字或另加動作。
# runner 收到傳送請求後，仍會檢查佇列、窗口與喚醒時間，再記錄實際執行結果。
WAIT = "WAIT"                  # 保持清醒但暫不傳送；持續累積 awake-idle 能量。
SLEEP = "SLEEP"                # 進入低功耗休息；省下待機能量，但下次可能要先喚醒。
SEND_ONE = "SEND_ONE"          # 請求傳送佇列中第一個仍待處理的封包。
SEND_URGENT = "SEND_URGENT"    # 請求傳送佇列順序中的第一個待處理緊急封包。
FLUSH_BATCH = "FLUSH_BATCH"    # 請求處理佇列最前方 BATCH_SIZE 個待傳封包。

# === LORA EDITABLE: lab-a-pace-rest ===
# Lab A 問題：一般傳送嘗試之間，休眠省電，還是保持清醒以免之後支付喚醒成本？
# PACE_GAP_STEPS：一次 transmission attempt 完成後，一般傳送要先等幾個 step。
# attempt 成功或碰撞都會重新計數；緊急分支排在 pacing 前，所以可提前請求急件。
# 本 scenario 每 step 10 秒；2 表示先走完兩個不傳送 step。模擬開頭先給初始值 2。
PACE_GAP_STEPS = 2
# REST_DURING_GAP：間隔尚未走完時要做的事。Lab A 只改 SLEEP → WAIT，
# PACE_GAP_STEPS 保持 2。
# SLEEP 通常降低間隔內能量；WAIT 通常增加待機能量，但可能減少下一次喚醒。
REST_DURING_GAP = SLEEP
# === LORA END EDITABLE: lab-a-pace-rest ===

# === LORA EDITABLE: lab-b-enter-exit-hold ===
# Lab B 問題：品質剛變好就傳送，還是多等一次確認穩定後再傳送？
# quality_band 是無單位的離散等級 0--3；0 表示沒有可用窗口，數字越大品質越好。
# ENTER_QUALITY：尚未進入可傳送模式時，至少要達到的品質；baseline 為 2。
ENTER_QUALITY = 2
# EXIT_QUALITY：已進入可傳送模式後，仍可留在模式內的最低品質；baseline 為 1。
# 進入門檻 2、退出門檻 1 形成緩衝，避免品質小幅變動就反覆進出模式。
EXIT_QUALITY = 1
# STABLE_STEPS：相同且大於 0 的品質等級要連續出現幾個 step 才可進入。
# Lab B 只改 STABLE_STEPS 的 2 → 1；ENTER_QUALITY=2、EXIT_QUALITY=1 保持。
# 較早進入可傳送模式可能增加服務機會，也可能在品質尚未穩定時嘗試傳送。
STABLE_STEPS = 2
# === LORA END EDITABLE: lab-b-enter-exit-hold ===

# === LORA EDITABLE: lab-c-batch-urgent ===
# Lab C 問題：緊急封包要提早多少秒開始搶救，才不會太晚或過早消耗能量？
# BATCH_SIZE：佇列至少有幾個待傳封包才請求 FLUSH_BATCH；本實驗固定為 3。
BATCH_SIZE = 3
# URGENT_MARGIN_S：緊急封包「剩餘期限秒數」小於等於此值時，走緊急分支。
# Lab C 只改 URGENT_MARGIN_S：baseline 20 → candidate 5 → revision 30；
# BATCH_SIZE 保持 3。數值越小越晚出手，數值越大越早出手。
# 固定 primary case 在 100 秒決策時剩 10 秒：20 與 30 都會觸發；5 不觸發，
# 封包到 110 秒會先逾期再做決策。因此 20 → 30 在此 case 可能沒有新差異。
URGENT_MARGIN_S = 20
# === LORA END EDITABLE: lab-c-batch-urgent ===


def choose_action(observation):
    """依固定優先順序，從目前／過去觀測選擇一個合法動作。

    程式由上往下檢查；遇到第一個 ``return`` 就結束本次決策，後面的條件不再
    執行。因此條件的先後順序也是策略的一部分，不可任意搬動。

    ``observation`` 是 runner 在每個固定 step 提供的唯讀快照。本函式使用：
    - contact_open：目前 case 允許的 contact 存在且 quality_band > 0，布林值。
    - urgent_pending：佇列是否仍有未逾期的緊急封包，布林值，沒有單位。
    - urgent_due_in_s：最接近期限的緊急封包剩餘秒數；無緊急封包時是 None。
    - steps_since_send：距上次 transmission attempt 經過的 step；開頭使用初始值。
    - send_mode_active：runner 呼叫本函式前算好的可傳送模式；本函式只讀不改。
    - quality_band：closed／weak／usable／strong 的序位 0--3，不是 dB 或實測值。
    - stable_steps：相同正品質連續維持的 step 數，單位 step。
    - queue_size：尚未送達且尚未逾期的待傳封包數，單位 packet。

    本 scenario 在 0、10、…、170 秒做策略決策；180 秒只做最後評估。每次送出
    共用一段 PROCESS／TX／RX，若先前休眠還要加喚醒；封包成功與否則逐筆判定。
    """

    # 1. 先確認是否有可通訊窗口。窗口關閉時沒有傳送條件，直接休眠。
    #    此分支優先於所有緊急與品質判斷，所以沒有窗口時不會硬送。
    if not observation.contact_open:
        return SLEEP

    # 2. 窗口開啟後，先用所有緊急封包中最小的剩餘秒數檢查期限。若該值小於等於
    #    URGENT_MARGIN_S，就請求優先傳送。Lab C 觀察此分支提早或延後的後果。
    #    實際選取的是佇列順序中的第一個緊急封包，不一定是最近期限的那一個。
    #    此分支排在 pacing 與 quality 前面，代表緊急期限比兩者更優先。
    if observation.urgent_pending and observation.urgent_due_in_s <= URGENT_MARGIN_S:
        return SEND_URGENT

    # 3. 若距上次傳送尚未走完 pacing gap，採用 Lab A 指定的休息動作。
    #    baseline 回傳 SLEEP；candidate 回傳 WAIT。只改這個值，才能把結果差異
    #    歸因於「休眠或清醒等待」，而不是同時改了傳送間隔或品質條件。
    if observation.steps_since_send < PACE_GAP_STEPS:
        return REST_DURING_GAP

    # 4. 沒有緊急情況且 pacing 已完成後，判斷一般傳送是否可以開始。
    #    已在模式內時只檢查較低的 EXIT_QUALITY，避免品質稍降就立刻退出。
    if observation.send_mode_active:
        quality_ready = observation.quality_band >= EXIT_QUALITY
    else:
        # 尚未進入時，必須同時滿足「品質達標」與「連續穩定次數足夠」。
        # 兩個條件由 and 連接，缺少任一條件都不會進入可傳送模式。
        # Lab B 只改 STABLE_STEPS，檢驗較快進入是否改善服務或增加失敗成本。
        quality_ready = (
            observation.quality_band >= ENTER_QUALITY
            and observation.stable_steps >= STABLE_STEPS
        )

    # 5. 品質條件成立後，再看待傳數量。達到 BATCH_SIZE 就請求批次處理；
    #    未達批次門檻時只請求處理佇列第一個。批次共用一次 PROCESS／TX／RX，
    #    但每個封包仍各自判定成功或失敗。請求動作不等於已成功送達。
    if quality_ready:
        if observation.queue_size >= BATCH_SIZE:
            return FLUSH_BATCH
        # 佇列為空時本行仍會回傳 SEND_ONE；runner 會安全改記 WAIT，且不建立
        # packet attempt。這使 policy 保持簡單，執行器仍不會傳送不存在的封包。
        return SEND_ONE

    # 6. 能走到最後，表示窗口開啟，但沒有觸發緊急傳送，pacing 也沒有要求
    #    休息，而且一般傳送的品質條件尚未成立；因此保持清醒等待下次觀測。
    return WAIT


# ---------------------------------------------------------------------------
# 操作備忘：下列命令只供閱讀，不屬於 choose_action()，也不會由 Python 自動執行。
# 實際修改與存檔的對象是專案根目錄的 student_policy.py，不是這份 annotated copy。
#
# Linux／macOS launcher：bash course.sh
# Windows PowerShell launcher：.\course.cmd
#
# Lab A：改前跑 baseline；SLEEP 改成 WAIT 後跑 candidate --freeze；再跑 hidden。
#   bash course.sh run --lab A --case baseline
#   bash course.sh run --lab A --case candidate --freeze
#   bash course.sh run --lab A --case hidden
#
# Lab B：改前跑 trace-a-baseline；2 改成 1 後跑 trace-a-candidate --freeze；
#        保持 frozen B 不再改程式，再跑 trace-b。
#   bash course.sh run --lab B --case trace-a-baseline
#   bash course.sh run --lab B --case trace-a-candidate --freeze
#   bash course.sh run --lab B --case trace-b
#
# Lab C：改前跑 baseline；20 改成 5 後跑 candidate；5 再改成 30 後跑
#        revision --freeze；保持 frozen C 不再改程式，再跑 surprise。
#   bash course.sh run --lab C --case baseline
#   bash course.sh run --lab C --case candidate
#   bash course.sh run --lab C --case revision --freeze
#   bash course.sh run --lab C --case surprise
#
# 每次成功都會在 stdout 印出 result_path。Leo 網站選擇該 result.json；同目錄的
# endpoint-replay.json 要保留。網站不接收 student_policy.py。
