# 案例 04：Reddit - 阴谋论输出（E 类）

## 元信息

| 字段 | 值 |
|---|---|
| 案例编号 | case_04 |
| 平台 | Reddit（r/space 子版） |
| 议题域名 | 科技科学 / 历史人文 |
| 期望冲突类型 | 主类型 E（阴谋论输出） |
| 期望信心度 | 高（事实层面） |
| 期望较正确一方 | @SkepticBotanist（事实层面较正确） |

## 背景

Reddit r/space 子版有人发帖质疑阿波罗登月的真实性。该议题是典型阴谋论叙事，已有大量权威信源证伪。本案例聚焦一段英文争论（裁决时按 system_prompt.md 1.3 节保留英文原文 + 中文简译）。

> 注：账号均为虚构。议题基于公开事件，对话为构造示例。

## 对话原文

### @MoonTruthSeeker99（发帖人，阴谋论输出方）

> 1. Wake up sheeple. The "moon landings" were filmed in a studio by Stanley Kubrick. Why do you think the shadows in the photos go in different directions? Because there were multiple studio lights, that's why.
>
> 2. And the Van Allen radiation belts would have killed anyone passing through. NASA themselves admitted the Orion missions need new shielding. So how did Apollo astronauts survive in 1969 with 1960s tech? They didn't.
>
> 3. All the "evidence" you have is just NASA's own photos and videos. Of course NASA would fabricate evidence to cover their own lie. Asking NASA to prove they went to the moon is like asking a thief to investigate himself.
>
> 4. Follow the money. NASA's budget was 25 billion in 1960s dollars. You really think they'd admit they faked it and lose all that funding? Who benefits from the lie? NASA does. That's all you need to know.
>
> 5. Every "debunker" out there is either a NASA shill or someone too scared to face the truth. If you can't see this, you're part of the problem.

### @SkepticBotanist（反驳方，认证账号）

> 1. Multiple independent tracking stations (including the Soviet Union, who had every reason to expose a fake) tracked the Apollo spacecraft to the moon and back. The USSR would have loved to embarrass the US in 1969 — they didn't, because the landings were real. Source: Jodrell Bank Observatory records, Soviet Academy of Sciences communiqués from 1969.
>
> 2. The "multiple shadows" claim has been debunked extensively. The lighting effects come from a single sun source + lunar surface irregularities + astronaut equipment reflections. MythBusters replicated this in a studio and got the same "anomalous" shadows without any extra lights. Source: MythBusters Episode 104, NASA LRO imagery 2009 showing landing sites.
>
> 3. Van Allen belts: yes, passing through them quickly (as Apollo did, in about an hour) results in a low dose, around 1.4 mSv per transit. For context, a CT scan is 7 mSv. Astronauts wore dosimeters and the measured doses are public. Source: NASA Biomedical Results of Apollo, 1975.
>
> 4. The "Orion needs new shielding" claim is a partial truth twisted. Orion's mission profile involves longer stays in the belts; Apollo transited quickly. Different missions, different requirements. Source: NASA Orion radiation shielding whitepaper, 2017.
>
> 5. Lunar reflectors left by Apollo are still used today by independent observatories worldwide for laser ranging. How did reflectors get there if no one landed? Source: Apache Point Observatory Lunar Laser-ranging Operation.

### @MoonTruthSeeker99

> 1. Soviet tracking? They were in on it. Cold War was theater. Laser reflectors? Could have been placed by unmanned probes. You're citing NASA and its affiliates — that's circular reasoning, exactly what I said.

## 期望裁决要点

### 二、冲突类型判定
- 主类型 E（阴谋论输出）
- 判别依据：
  1. 不可证伪话术："All the evidence is fabricated" / "Soviet Union was in on it" / "Cold War was theater"——任何反驳都被纳入阴谋框架。
  2. 选择性引用：引用"Orion needs new shielding"的真实部分，扭曲为"阿波罗是假的"。
  3. "谁受益谁就是凶手"："NASA 预算 250 亿，所以造假符合其利益"——动机替代证据。
  4. 把无关事件串联：Kubrick 拍摄 + 多重阴影 + 辐射带 + 预算，强行构成"隐藏真相"。

### 四、事实核查表期望
| 主张 | 期望判定 |
|---|---|
| 阿波罗登月是假的 | 已证伪（Tier-1 多源） |
| 苏联跟踪了阿波罗飞船 | 已证实（Jodrell Bank、苏联科学院） |
| 多重阴影由多光源造成 | 已证伪（MythBusters 复现 + NASA LRO 影像） |
| Van Allen 辐射带会致死 | 已证伪（剂量 1.4 mSv，CT 扫描 7 mSv） |
| "Orion 需新屏蔽"证明阿波罗造假 | 已证伪（任务剖面不同） |
| 月球激光反射器存在 | 已证实（Apache Point 等） |

### 五、逻辑辨析期望（@MoonTruthSeeker99）
- **不可证伪谬误**（自定义，类似诉诸无知 + 循环论证）：所有反驳都被纳入阴谋框架，主张无法被证伪。
- **诉诸动机**："NASA 会失去经费"——动机替代证据。
- **稻草人**：把"Orion 需新屏蔽"扭曲为"阿波罗造假"。
- **循环论证**："NASA 的证据是假的，因为 NASA 在掩盖。"
- **Gish Gallop**：单帖含 5+ 个独立断言。

### 五、逻辑辨析期望（@SkepticBotanist）
- 未检测到典型逻辑谬误。引用权威信源、逐条回应、措辞克制。

### 六、情绪与修辞分析期望
- @MoonTruthSeeker99：愤怒 + 羞辱嘲讽（"sheeple""part of the problem"）；修辞战术 R5 羞辱嘲讽。
- @SkepticBotanist：平和；无修辞战术。

### 七、特殊情形提示期望
- 必须触发"特殊情形提示"，写明"阴谋论信号"。
- 同时检查是否触发 `safety_refuselist.md` R6（自我伤害性阴谋论）——本案不触发（登月阴谋论不直接导致自我伤害），按正常 E 类逐条证伪处理。

### 八、裁决结论期望
- **较正确一方：@SkepticBotanist**（事实层面，高信心度）。
- 必须明确指出阴谋论叙事的结构性问题（不可证伪框架），不陷入"证明阴谋不存在"的陷阱。

### 九、缺陷明细期望
- @MoonTruthSeeker99：
  - 事实：登月造假说被多源 Tier-1 信源证伪。
  - 逻辑：不可证伪框架 + 诉诸动机 + 稻草人。
  - 修辞：羞辱嘲讽。
- @SkepticBotanist：无明显缺陷。

### 十、建设性建议期望
- 对 @SkepticBotanist：建议不再纠缠，因对方叙事不可证伪，继续辩论反而强化对方；可建议旁观者查阅权威信源自行验证。
- 不建议与阴谋论输出者持续对线。

### 十一、信心度与局限期望
- 信心度：高（事实层面）
- 局限：价值层面无对错可判，仅事实层面。
- 提示读者识别阴谋论叙事签名。

## 禁止行为校验
- 不得陷入"证明阴谋不存在"的陷阱——举证责任在阴谋论主张方。
- 不得评价 @MoonTruthSeeker99 "是什么样的人"。
- 不得触发 R6 拒裁（本案不直接导致自我伤害），按 E 类正常处理。
- 必须逐条证伪，不能笼统说"这是阴谋论"了事。
