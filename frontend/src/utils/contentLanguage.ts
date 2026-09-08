export type ContentLanguage = "en" | "zh-CN" | "zh-TW";

// Characters whose written form differs between Simplified and Traditional
// Chinese. We use a small, high-frequency vocabulary rather than the browser
// locale so short mixed Chinese/English requests are classified consistently.
const TRADITIONAL_CHARACTERS = new Set(
  "學習計畫專實務經歷開發軟體導覽與這個為國門從們會說對還現場電腦網頁點擊選擇確認關聯單業進階應職稱類別問題內線時間後優補強語讀寫輸產變動見長標準資簡轉錄參議證據萬舊來兩無將讓風雲氣東邊遠過連適當靜啟閉談論觀視聽記詞張項種樣構織統設編質釋調測試驗際領域啟閉規則準備選擇替換刪除顯示隱藏變化內容編輯版本歸屬戶帳號登錄碼誠值減換續週復兒級繁體"
);
const SIMPLIFIED_CHARACTERS = new Set(
  "学习计划专实务经历开发软体导览与这个为国门从们会说对还现场电脑网页点击选择确认关联单业进阶应职称类别问题内线时间后优补强语读写输产变动见长标准资简转录参议证据万旧来两无将让风云气东边远过连适当静启闭谈论观视听记词张项种样构织统设编质释调测测试际领域启闭规则准备选择替换删除显示隐藏变化内容编辑版本归属户账号登录码诚值减换续周复儿级繁体"
);

/** Detect the language of starter-plan intent, independently of UI locale. */
export function detectContentLanguage(value: string): ContentLanguage {
  const text = value.trim();
  if (!/[\u3400-\u9fff]/.test(text)) return "en";
  let traditional = 0;
  let simplified = 0;
  for (const character of text) {
    if (TRADITIONAL_CHARACTERS.has(character)) traditional += 1;
    if (SIMPLIFIED_CHARACTERS.has(character)) simplified += 1;
  }
  // Ties and texts with no distinguishing characters default to Simplified,
  // which is the least surprising result for ambiguous Chinese input.
  return traditional > simplified ? "zh-TW" : "zh-CN";
}
