# ASTER_01 合格视觉资产包（2026-08-31）

本包集中保存此前生成且通过对应阶段检查的 ASTER_01 贴图与配套视觉图片，便于公开仓库下载、版本对照和后续复用。

## 推荐使用顺序

1. **v5 Gemini 收敛贴图**：正式基线，已完成最终 Gemini sign-off 与多视角/Mipmap QA。
2. **v4 Gemini 贴图**：上一阶段 Gemini 版本，用于历史对照。
3. **v3 贴图**：早期生成版本，用于迭代回溯。

## 包内结构

- `textures/`：v3、v4 Gemini、v5 Gemini 收敛版 BaseColor 贴图。
- `images/`：Image2 艺术方向图、各阶段正背面预览、评审图、v5 八视角接触表和 Mipmap 检查图。

本包只收录符合阶段要求的生成贴图与视觉图片；模型快照、原始参考图、调试遮罩、NumPy 缓冲区和历史 ZIP 不包含在内。

## 文件校验（SHA-256）

| 文件 | 说明 | 大小（字节） | SHA-256 |
|---|---|---:|---|
| `textures/ASTER_01_BASE_COLOR_v3.png` | v3 生成贴图 | 30058470 | `4f39719976cba3219fdca0943fafc327b4c46f2beaa385860f5a886c7c1e119c` |
| `textures/ASTER_01_BASE_COLOR_v4_gemini.png` | v4 Gemini 生成贴图 | 31351375 | `4572dd93563381077d53066a3d00e235f2cad1e4a47136008ca457bd5e80a12a` |
| `textures/ASTER_01_BASE_COLOR_v5_gemini_converged.png` | v5 Gemini 收敛贴图 | 31330290 | `f5d1565cd74c32ee4342f81c3bf733fd97b4d61e7398aad00d19bb1eba5aac19` |
| `images/v3_gpt_image2_art_direction.png` | v3 Image2 正面艺术方向图 | 1589735 | `2d97109df3b6f397c5e64fd62bd7a7c109d6357986ff53a16027e16ccc65dedb` |
| `images/v3_gpt_image2_back_art_direction.png` | v3 Image2 背面艺术方向图 | 1557571 | `b18b07b0a6f67e4a59d01951d84b00ef7c4373e814cd0ba1938f1ea5a529a850` |
| `images/v3_review_board.png` | v3 最终评审图 | 1314738 | `98683499ccb0a94e6791a7518be7fd3b5274051d255f7593d04e8c11d44e4384` |
| `images/v3_front.png` | v3 正面预览 | 190517 | `1a19efee5e5ca9e6be3dad0770dcfc029531ba2c32858058e03eaf755a3a1673` |
| `images/v3_back.png` | v3 背面预览 | 160648 | `11202a54355b5ae580f05fc68a73c9fe1f7945b0bc3c17f67f974b7e1a4d56ec` |
| `images/v4_review_board.png` | v4 Gemini 最终评审图 | 431311 | `61e6faebb5d016ae748581bb6465da20c97bf60bb0c5bab334e4ab2680f77fab` |
| `images/v4_front.png` | v4 Gemini 正面预览 | 195760 | `72ae882c6f906f9e2c3939db6eec0909aec86c1a4c6114150b0a0028eabf884e` |
| `images/v4_back.png` | v4 Gemini 背面预览 | 167905 | `e5465610817a31fbbedf57c630a0e9d5065939aa590609a5ed9116c76e853258` |
| `images/v5_front.png` | v5 收敛版正面预览 | 195728 | `01b6d30f9674a83d5122cba0b5fcfb10dcb0d3f832028645806f4f9cd6274382` |
| `images/v5_back.png` | v5 收敛版背面预览 | 167876 | `8b2e40b30f7d07e0977e72e1e779102eb3777cd658f1140e338706fc4b8b5937` |
| `images/v5_final_multiview_contact_sheet.png` | v5 八视角接触表 | 309599 | `a97bfb07818007fddeb83bab1b850c2b47429488e7e09dff235541fe81065169` |
| `images/v5_mipmap_0_4_contact_sheet.png` | v5 Mipmap 0–4 检查图 | 251223 | `38212b0c1a65b69bbfacf33036ffb3d8215c3c8a2abf632b8e8e168bf3e88333` |

原始资产合计：15 个文件，99272746 字节。

## 仓库对应位置

- v3：`outputs/ASTER_01_v3_texture_tune_20260830/`
- v4：`outputs/ASTER_01_v4_gemini_texture_tune_20260830/`
- v5：`outputs/ASTER_01_v5_gemini_converged_20260831/`
