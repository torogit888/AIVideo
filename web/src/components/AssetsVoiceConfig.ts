export const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

export const OMNIVOICE_CATEGORIES = [
  {
    category: "gender",
    label: "性別",
    options: [
      { label: "女", value: "女" },
      { label: "男", value: "男" },
    ],
  },
  {
    category: "age",
    label: "年齡層",
    options: [
      { label: "兒童", value: "儿童" },
      { label: "少年", value: "少年" },
      { label: "青年", value: "青年" },
      { label: "中年", value: "中年" },
      { label: "老年", value: "老年" },
    ],
  },
  {
    category: "pitch",
    label: "音高",
    options: [
      { label: "極低音", value: "极低音调" },
      { label: "低音", value: "低音调" },
      { label: "中音", value: "中音调" },
      { label: "高音", value: "高音调" },
      { label: "極高音", value: "极高音调" },
    ],
  },
  {
    category: "dialect",
    label: "中文口音",
    options: [
      { label: "標準普通話", value: "" },
      { label: "東北話", value: "东北话" },
      { label: "四川話", value: "四川话" },
      { label: "陝西話", value: "陕西话" },
      { label: "河南話", value: "河南话" },
      { label: "貴州話", value: "贵州话" },
      { label: "雲南話", value: "云南话" },
      { label: "桂林話", value: "桂林话" },
      { label: "青島話", value: "青岛话" },
      { label: "濟南話", value: "济南话" },
      { label: "甘肅話", value: "甘肃话" },
      { label: "寧夏話", value: "宁夏话" },
      { label: "石家莊話", value: "石家庄话" },
    ],
  },
  {
    category: "style",
    label: "氣音",
    options: [
      { label: "一般講述", value: "" },
      { label: "耳語 / 氣音", value: "耳语" },
    ],
  },
];

export const OMNIVOICE_PRESETS = [
  { label: "沉穩男聲", instruct: "男，中年，低音调" },
  { label: "知性女聲", instruct: "女，青年，中音调" },
  { label: "懸疑氣音", instruct: "男，青年，低音调，耳语" },
  { label: "長者說書", instruct: "男，老年，低音调" },
  { label: "活潑少女", instruct: "女，少年，高音调" },
  { label: "四川口吻", instruct: "男，中年，中音调，四川话" },
  { label: "東北評書", instruct: "男，中年，高音调，东北话" },
];

const ORDER_MAP: Record<string, number> = {
  女: 1, 男: 1, female: 1, male: 1,
  儿童: 2, 少年: 2, 青年: 2, 中年: 2, 老年: 2, child: 2, teenager: 2, "young adult": 2, "middle-aged": 2, elderly: 2,
  极低音调: 3, 低音调: 3, 中音调: 3, 高音调: 3, 极高音调: 3, "very low pitch": 3, "low pitch": 3, "moderate pitch": 3, "high pitch": 3, "very high pitch": 3,
  河南话: 4, 陕西话: 4, 四川话: 4, 贵州话: 4, 云南话: 4, 桂林话: 4, 济南话: 4, 石家庄话: 4, 甘肃话: 4, 宁夏话: 4, 青岛话: 4, 东北话: 4,
  耳语: 5, whisper: 5,
};

export const updateVoiceInstructTag = (
  current: string,
  categoryOptions: { label: string; value: string }[],
  selectedValue: string
): string => {
  let parts = current
    .split(/[,，]/)
    .map((s) => s.trim())
    .filter(Boolean);

  const allCategoryVals = new Set(categoryOptions.map((o) => o.value).filter(Boolean));
  parts = parts.filter((p) => !allCategoryVals.has(p));

  if (selectedValue) {
    parts.push(selectedValue);
  }

  parts.sort((a, b) => (ORDER_MAP[a] || 99) - (ORDER_MAP[b] || 99));
  return parts.join("，");
};
