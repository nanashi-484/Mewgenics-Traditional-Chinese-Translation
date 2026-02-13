# 《Mewgenics》繁體中文補丁  
# Mewgenics Chinese Translation Patch

### 本專案基於[rainzz-512/Mewgenics-Chinese-Translation](https://github.com/rainzz-512/Mewgenics-Chinese-Translation)進行修改，非常感謝原作者*Rain Zhao*

## 中文說明

本專案提供 **《Mewgenics》繁體中文補丁**，目前已覆蓋遊戲大部分文本，包括：

- NPC 對話  
- 物品與技能說明  
- UI 介面文本  
- 主要遊戲內容文本  

本補丁採用 **AI 輔助翻譯 + 遊戲內測試校對** 的方式製作，後續版本將持續優化翻譯品質與術語統一。  
歡迎提交反饋和修正建議。

### v0.3 更新內容
- 修復並優化殘留的部分文字擠壓、縮小顯示問題
- 補充部分未翻譯與翻譯不完整的文本
- 統一部分關鍵字翻譯（如 `Thorns` 統一為「荊棘」、`Bruise` 統一為「挫傷」）

### v0.2 更新內容
- 修正 `[img:...]` 標籤解析錯誤導致的 parse error 與可能的遊戲崩潰問題
- 最佳化技能與物品描述文字排版，解決文字過長導致卡面字體過小、顯示擁擠的問題
- 恢復 `en` 列原版英文文本，修復語言無法正常切換的問題
- 多項文字細節與排版優化

### 安裝方法
1. 在 **Releases** 頁面下載最新補丁  
2. 將補丁中的 `data` 資料夾解壓到遊戲目錄（與 `resources.gpak` 同級）  
```
ex: resources.gpak
    steam_api64.dll
    data/
    └──text/
        ├── abilities
        ...
```
3. 啟動遊戲即可顯示中文

### 注意
- 當前為早期版本，可能仍存在少量未翻譯文本  
- 若遊戲更新導致文本失效，請等待補丁更新

### 可選：自訂中文字體

遊戲預設使用 Noto Sans CJK TC（思源黑體）作為字體的 fallback 選項。如果你希望更換為其他字體，有兩種方式：

**方式一：使用預製字體（倉耳漁陽體）**
1. 將補丁中的 `swfs` 資料夾複製到遊戲目錄（與 `resources.gpak` 同級）
2. 重啟遊戲即可看到效果

> [倉耳漁陽體](https://tsanger.cn/product/199)為免費商用字體。效果預覽見下方截圖。

**方式二：DIY 替換為任意字型**
1. 安裝 [JPEXS FFDec](https://github.com/jindrapetrik/jpexs-decompiler)
2. 在 JPEXS FFDec 安裝目錄下執行以下命令（以補丁自帶的 `swfs/unicodefont.swf` 為基礎）：
 ```
 ffdec-cli.exe -replace unicodefont.swf unicodefont_custom.swf 1 你的字型.ttf
 ```
3. 將產生的 `unicodefont_custom.swf` 重新命名為 `unicodefont.swf`，放入遊戲目錄的 `swfs/` 資料夾

> 注意：字體檔案放在遊戲根目錄的 `swfs/` 資料夾下（不是 `data/swfs/`）。
```
ex: resources.gpak
    steam_api64.dll
    data/
    swfs/
```

**恢復預設字體：** 刪除遊戲目錄下的 `swfs/` 資料夾即可。

**效果預覽：**

| | 預設字體（思源黑體） | 自訂字體（倉耳漁陽體） |
|:---:|:---:|:---:|
| 主選單 | ![預設-主選單](screenshots/font_default_main_menu.png) | ![倉耳漁陽體-主選單](screenshots/font_canger_yuyang_main_menu.png) |
| 遊戲設定 | ![預設-遊戲設定](screenshots/font_default_settings_game.png) | ![倉耳漁陽體-遊戲設定](screenshots/font_canger_yuyang_settings_game.png) |

---

## English

This project provides a **Chinese translation patch for Mewgenics**, covering most in-game texts including:

- NPC dialogues  
- Items and abilities  
- UI texts  
- General gameplay text  

The translation is created using **AI-assisted translation and in-game testing**, and future updates will continue to improve translation quality and terminology consistency.  
Feedback and correction suggestions are welcome.

### Installation
1. Download the latest patch from **Releases**  
2. Extract the `data` folder into the game directory (the same location as `resources.gpak`)  
3. Overwrite files if prompted  
4. Launch the game — the text should now appear in Chinese

### Notes
- This is an early release; some lines may remain untranslated  
- If a game update breaks the patch, please wait for a new version