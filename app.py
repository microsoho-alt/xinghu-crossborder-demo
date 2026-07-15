from dataclasses import dataclass
from datetime import datetime
import hashlib
import html
import time
from typing import Dict, List, Tuple
from uuid import uuid4

import streamlit as st

from diagnosis_client import DiagnosisApiClient, DiagnosisApiError, ImageAsset


# =========================================================
# 星狐 AI 跨境商品诊断舱 v5
# 外部演示增强版：
# 1. 三类演示案例下拉选择，一键自动填写
# 2. 报告结构升级为可交付版：摘要、评分、平台、风险、财务、任务、路线图
# 3. 页面更偏商业演示和交付报告表达
# =========================================================


@dataclass
class ProductInput:
    name: str
    category: str
    factory_price_cny: float
    retail_price_usd: float
    exchange_rate: float
    platform_commission_rate: float
    estimated_logistics_cny: float
    weight_g: float
    length_cm: float
    width_cm: float
    height_cm: float
    material: str
    has_battery: bool
    has_magnet: bool
    is_liquid_or_powder: bool
    is_fragile: bool
    certifications: List[str]
    customer_type: str
    business_goal: str
    product_description: str


MAX_SCORES = {
    "市场需求适配度": 20,
    "平台销售适配度": 15,
    "利润空间适配度": 20,
    "物流履约适配度": 15,
    "合规风险可控度": 15,
    "内容传播适配度": 10,
    "竞争强度修正值": 5,
}


SAMPLE_CASES = {
    "案例1：C端红海消费品｜车载手机支架": {
        "name": "车载手机支架",
        "category": "汽配 手机支架 汽车用品",
        "factory_price_cny": "18",
        "retail_price_usd": "9.99",
        "exchange_rate": "7.2",
        "platform_commission_rate": "0.15",
        "estimated_logistics_cny": "18",
        "weight_g": "200",
        "length_cm": "10",
        "width_cm": "8",
        "height_cm": "5",
        "material": "ABS塑料",
        "has_battery": False,
        "has_magnet": False,
        "is_liquid_or_powder": False,
        "is_fragile": False,
        "certifications": ["无"],
        "customer_type": "C端消费者",
        "business_goal": "测品",
        "product_description": "用于汽车出风口或中控台固定手机，适合导航、充电、长途驾驶场景。产品安装方便，客单价低，海外需求存在，但同质化严重，需要通过细分场景、套装组合和内容素材做差异化测试。",
    },
    "案例2：B端工业品｜硬质合金铣刀": {
        "name": "硬质合金铣刀",
        "category": "工业刀具 机械加工 五金工具",
        "factory_price_cny": "45",
        "retail_price_usd": "28.99",
        "exchange_rate": "7.2",
        "platform_commission_rate": "0.08",
        "estimated_logistics_cny": "12",
        "weight_g": "80",
        "length_cm": "12",
        "width_cm": "3",
        "height_cm": "3",
        "material": "钨钢",
        "has_battery": False,
        "has_magnet": False,
        "is_liquid_or_powder": False,
        "is_fragile": True,
        "certifications": ["无"],
        "customer_type": "工厂客户",
        "business_goal": "找订单",
        "product_description": "用于CNC数控加工、模具加工和金属切削场景，目标客户为海外加工厂、五金经销商和工业品采购商。产品依赖参数、耐用性、样品测试和批量采购转化，更适合B2B询盘和行业独立站获客。",
    },
    "案例3：带电小家电｜便携式迷你吸尘器": {
        "name": "便携式迷你吸尘器",
        "category": "小家电 消费电子 家居清洁",
        "factory_price_cny": "68",
        "retail_price_usd": "29.99",
        "exchange_rate": "7.2",
        "platform_commission_rate": "0.15",
        "estimated_logistics_cny": "38",
        "weight_g": "850",
        "length_cm": "25",
        "width_cm": "15",
        "height_cm": "12",
        "material": "ABS塑料 锂电池",
        "has_battery": True,
        "has_magnet": False,
        "is_liquid_or_powder": False,
        "is_fragile": False,
        "certifications": ["CE", "RoHS"],
        "customer_type": "C端消费者",
        "business_goal": "做品牌",
        "product_description": "面向车内清洁、桌面清洁、宠物毛发清理等高频生活场景，适合短视频展示和场景化种草。产品带电，涉及物流渠道、平台审核和目标市场认证要求，需要提前核查电池运输、CE/RoHS/FCC等合规资料。",
    },
}


PLATFORM_RULES = {
    "Amazon": {
        "适合": ["中高客单价", "认证齐全", "物流稳定", "品牌化"],
        "限制": ["合规要求高", "评价冷启动难", "广告成本高"],
    },
    "AliExpress": {
        "适合": ["低客单价", "快速测品", "轻小件", "供应链价格优势"],
        "限制": ["价格竞争激烈", "品牌溢价弱"],
    },
    "TikTok Shop": {
        "适合": ["强场景展示", "冲动消费", "短视频种草", "C端产品"],
        "限制": ["内容供给要求高", "爆品生命周期短"],
    },
    "独立站": {
        "适合": ["高毛利", "品牌化", "复购", "私域沉淀"],
        "限制": ["投流能力要求高", "信任建设周期长"],
    },
    "B2B平台": {
        "适合": ["工业品", "定制品", "工厂客户", "询盘"],
        "限制": ["成交周期长", "样品和交付能力要求高"],
    },
}


def load_css():
    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            font-family: "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", sans-serif;
        }
        .block-container {
            padding-top: 1.4rem;
            max-width: 1220px;
        }
        .hero {
            padding: 30px 34px;
            border-radius: 24px;
            background: radial-gradient(circle at 88% 18%, rgba(190, 148, 64, .2), transparent 24%), linear-gradient(135deg, #132420 0%, #193c34 58%, #205246 100%);
            color: #f8f4e8;
            margin-bottom: 22px;
            box-shadow: 0 16px 42px rgba(15, 23, 42, 0.22);
        }
        .hero h1 {
            font-size: 36px;
            line-height: 1.15;
            margin: 0 0 10px 0;
            letter-spacing: -0.6px;
        }
        .hero p {
            margin: 0;
            color: rgba(255, 255, 255, .84);
            font-size: 15px;
        }
        .pill {
            display: inline-block;
            margin-bottom: 14px;
            padding: 6px 12px;
            border-radius: 999px;
            background: rgba(255, 255, 255, .14);
            color: rgba(255, 255, 255, .94);
            font-size: 13px;
        }
        .section-card {
            padding: 20px 22px;
            border-radius: 18px;
            background: #ffffff;
            border: 1px solid #e5e7eb;
            box-shadow: 0 8px 28px rgba(15, 23, 42, 0.04);
            margin-bottom: 16px;
        }
        .metric-card {
            padding: 18px 20px;
            border-radius: 18px;
            background: #ffffff;
            border: 1px solid #e5e7eb;
            box-shadow: 0 8px 26px rgba(15, 23, 42, 0.05);
            min-height: 114px;
        }
        .metric-label {
            font-size: 13px;
            color: #64748b;
            margin-bottom: 8px;
        }
        .metric-value {
            font-size: 28px;
            font-weight: 800;
            color: #0f172a;
            line-height: 1.12;
        }
        .metric-sub {
            margin-top: 6px;
            font-size: 13px;
            color: #64748b;
        }
        .tag {
            display: inline-block;
            padding: 6px 10px;
            margin: 4px 6px 4px 0;
            border-radius: 10px;
            font-size: 13px;
            background: #eff6ff;
            color: #1d4ed8;
            border: 1px solid #bfdbfe;
        }
        .risk {
            background: #fff7ed;
            color: #c2410c;
            border: 1px solid #fed7aa;
        }
        .ok {
            background: #ecfdf5;
            color: #047857;
            border: 1px solid #a7f3d0;
        }
        .dark {
            background: #f1f5f9;
            color: #334155;
            border: 1px solid #cbd5e1;
        }
        .small-title {
            font-size: 18px;
            font-weight: 800;
            color: #0f172a;
            margin: 0 0 14px 0;
        }
        .footer-note {
            padding: 14px 16px;
            border-radius: 14px;
            background: #f8fafc;
            color: #475569;
            font-size: 13px;
            border: 1px solid #e2e8f0;
        }
        .report-title {
            padding: 20px 22px;
            border-radius: 18px;
            background: linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%);
            border: 1px solid #dbeafe;
            margin: 12px 0 18px 0;
        }
        .report-title h2 {
            margin: 0 0 8px 0;
            font-size: 26px;
            color: #0f172a;
        }
        .report-title p {
            margin: 0;
            color: #64748b;
            font-size: 14px;
        }
        div[data-testid="stForm"] {
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 20px;
            background: #ffffff;
            box-shadow: 0 8px 28px rgba(15, 23, 42, 0.04);
        }
        .evidence-shell {
            position: relative;
            overflow: hidden;
            padding: 24px;
            border-radius: 20px;
            border: 1px solid #d8d3c8;
            background: linear-gradient(145deg, #fffef9 0%, #f6f3ea 100%);
            box-shadow: 0 16px 40px rgba(34, 31, 24, .08);
            margin: 12px 0 18px;
        }
        .evidence-shell::before {
            content: "EVIDENCE LEDGER";
            position: absolute;
            right: -8px;
            top: 18px;
            color: rgba(36, 48, 47, .08);
            font: 800 28px Georgia, serif;
            letter-spacing: 3px;
        }
        .evidence-kicker { color: #a53a2a; font: 700 12px Georgia, serif; letter-spacing: 1.6px; text-transform: uppercase; }
        .evidence-title { color: #24302f; font: 800 25px Georgia, "Songti SC", serif; margin: 7px 0; }
        .evidence-note { color: #5d625d; font-size: 13px; max-width: 760px; }
        .claim-card { border-left: 4px solid #147d78; background: #f7fbf9; padding: 14px 16px; border-radius: 4px 14px 14px 4px; margin: 8px 0; }
        .claim-card.risk-red { border-left-color: #aa3328; background: #fff6f3; }
        .claim-card.risk-yellow { border-left-color: #c88b21; background: #fffaf0; }
        .claim-meta { color: #6c706b; font-size: 12px; margin-top: 6px; }
        .source-chip { display:inline-block; border:1px solid #c9c5b9; border-radius:999px; padding:3px 8px; margin-right:5px; font-size:11px; color:#525650; background:#fff; }
        .source-chip.evidence { color:#0f6d64; border-color:#8dc8be; }
        .source-chip.inference { color:#795b16; border-color:#d7bd76; }
        .source-chip.unknown { color:#9c3328; border-color:#d7a49f; }
        .image-frame { border:1px dashed #b8b2a5; border-radius:16px; padding:10px; background:#faf8f1; }
        .journey-kicker { color:#8b6b2b; font-size:12px; font-weight:800; letter-spacing:1.4px; text-transform:uppercase; }
        .journey-title { font-family:"Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", serif; font-size:28px; color:#172b26; margin:4px 0 8px; }
        .completion-shell { padding:14px 16px; border:1px solid #d9d2c4; background:#fbfaf6; border-radius:14px; margin:10px 0 18px; }
        .cockpit { border:1px solid #cfc8b9; border-radius:24px; padding:28px; background:linear-gradient(145deg,#fffef9,#f3f0e7); box-shadow:0 18px 50px rgba(31,45,39,.10); margin:12px 0 20px; }
        .cockpit.conditional { border-top:7px solid #b77a16; }
        .cockpit.proceed { border-top:7px solid #17745e; }
        .cockpit.pause { border-top:7px solid #a72e2e; }
        .decision-eyebrow { font-size:12px; font-weight:850; letter-spacing:1.5px; color:#6d7169; }
        .decision-label { font-family:"Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", serif; font-size:40px; line-height:1.1; color:#172b26; margin:9px 0; }
        .decision-reason { font-size:17px; line-height:1.7; color:#35443f; max-width:900px; }
        .confidence-line { margin-top:14px; color:#6a6e67; font-size:13px; }
        .signal-card { height:100%; padding:17px; border-radius:16px; border:1px solid #d9d4c8; background:#fff; }
        .signal-card.opportunity { border-top:4px solid #17745e; background:#f5fbf7; }
        .signal-card.blocking { border-top:4px solid #a72e2e; background:#fff7f5; }
        .signal-rank { color:#77766f; font-size:11px; font-weight:800; letter-spacing:1px; }
        .signal-title { color:#1c332d; font-size:16px; font-weight:850; margin:7px 0; }
        .signal-meaning { color:#535e59; font-size:13px; line-height:1.55; }
        .action-card { padding:16px 18px; border-left:4px solid #b77a16; background:#fffaf0; border-radius:4px 14px 14px 4px; margin:8px 0; }
        .threshold { color:#6d581f; font-size:12px; margin-top:5px; }
        .delta-up { color:#126b55; font-weight:800; }
        .delta-down { color:#a72e2e; font-weight:800; }
        @media (max-width: 640px) {
          .block-container { padding: .75rem .8rem 2rem; }
          .hero { padding:22px 19px; border-radius:18px; }
          .hero h1 { font-size:29px; }
          .cockpit { padding:20px 17px; border-radius:18px; }
          .decision-label { font-size:31px; }
          .decision-reason { font-size:15px; }
          .metric-value { font-size:23px; overflow-wrap:anywhere; }
          [data-testid="stDataFrame"], [data-testid="stTable"] { overflow-x:auto; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def clamp(value: float, min_value: int, max_value: int) -> int:
    return int(max(min_value, min(max_value, round(value))))


def contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword.lower() in text.lower() for keyword in keywords)


def parse_float(label: str, value: str, errors: List[str], required: bool = True, min_value: float = 0.0) -> float:
    text = str(value).strip()
    if not text:
        if required:
            errors.append(f"{label}不能为空。")
        return 0.0
    text = text.replace("，", ".").replace(",", "")
    try:
        num = float(text)
    except ValueError:
        errors.append(f"{label}必须填写数字。")
        return 0.0
    if num < min_value:
        errors.append(f"{label}不能小于{min_value}。")
        return 0.0
    return num


def actual_weight_kg(product: ProductInput) -> float:
    return round(product.weight_g / 1000, 3)


def volume_weight_kg(product: ProductInput) -> float:
    return round(product.length_cm * product.width_cm * product.height_cm / 6000, 3)


def chargeable_weight_kg(product: ProductInput) -> float:
    return round(max(actual_weight_kg(product), volume_weight_kg(product)), 3)


def retail_price_cny(product: ProductInput) -> float:
    return round(product.retail_price_usd * product.exchange_rate, 2)


def platform_commission_cny(product: ProductInput) -> float:
    return round(retail_price_cny(product) * product.platform_commission_rate, 2)


def estimated_single_profit_cny(product: ProductInput) -> float:
    profit = retail_price_cny(product) - product.factory_price_cny - product.estimated_logistics_cny - platform_commission_cny(product)
    return round(profit, 2)


def estimated_margin_rate(product: ProductInput) -> float:
    retail = retail_price_cny(product)
    if retail <= 0:
        return 0.0
    return round(estimated_single_profit_cny(product) / retail, 3)


def break_even_ad_cost(product: ProductInput) -> float:
    return max(0.0, round(estimated_single_profit_cny(product), 2))


def normalize_certifications(certs: List[str]) -> List[str]:
    return [c for c in certs if c and c != "无"]


def build_feature_vector(product: ProductInput) -> Dict:
    margin = estimated_margin_rate(product)
    c_weight = chargeable_weight_kg(product)
    certs = normalize_certifications(product.certifications)

    if product.retail_price_usd < 15:
        price_band = "低客单价"
    elif product.retail_price_usd <= 80:
        price_band = "中客单价"
    else:
        price_band = "高客单价"

    if c_weight <= 0.5:
        logistics_band = "轻小件"
    elif c_weight <= 2:
        logistics_band = "中等重量"
    else:
        logistics_band = "重货/大件"

    sensitive_flags = []
    if product.has_battery:
        sensitive_flags.append("带电")
    if product.has_magnet:
        sensitive_flags.append("带磁")
    if product.is_liquid_or_powder:
        sensitive_flags.append("液体/粉末")
    if product.is_fragile:
        sensitive_flags.append("易碎")

    category_text = f"{product.category} {product.name}"
    b2b_keywords = ["工业", "机械", "刀具", "模具", "设备", "零部件", "轴承", "传感器", "制动", "铸件", "冲压件", "OEM", "耗材", "工厂"]
    consumer_keywords = ["家居", "小家电", "宠物", "户外", "美妆", "服饰", "消费电子", "汽车用品", "手机支架", "车载", "收纳", "脚垫", "香薰", "厨房"]

    industrial_flag = contains_any(category_text, b2b_keywords) or product.customer_type == "工厂客户"
    consumer_flag = contains_any(category_text, consumer_keywords) or product.customer_type == "C端消费者"

    if product.customer_type == "C端消费者" and not contains_any(category_text, b2b_keywords):
        industrial_flag = False

    if industrial_flag and consumer_flag:
        product_type = "混合型产品"
    elif industrial_flag:
        product_type = "B端工业/供应链产品"
    elif consumer_flag:
        product_type = "C端消费品"
    else:
        product_type = "待进一步判定产品"

    return {
        "产品类型判定": product_type,
        "价格带": price_band,
        "海外零售价人民币口径": retail_price_cny(product),
        "出厂价": product.factory_price_cny,
        "估算平台佣金": platform_commission_cny(product),
        "估算单件物流费": product.estimated_logistics_cny,
        "估算单件利润": estimated_single_profit_cny(product),
        "扣费后利润率": margin,
        "单件最大可承受广告成本": break_even_ad_cost(product),
        "实际重量kg": actual_weight_kg(product),
        "体积重kg": volume_weight_kg(product),
        "计费重量kg": c_weight,
        "物流重量带": logistics_band,
        "物流敏感属性": "、".join(sensitive_flags) if sensitive_flags else "无",
        "认证数量": len(certs),
        "已有认证": "、".join(certs) if certs else "无",
        "客户类型": product.customer_type,
        "企业诉求": product.business_goal,
        "工业品倾向": "是" if industrial_flag else "否",
        "消费品倾向": "是" if consumer_flag else "否",
        "描述完整度": "较完整" if len(product.product_description) >= 30 else "偏弱",
    }


def match_platform_rules(product: ProductInput, vector: Dict) -> Dict[str, Dict]:
    result = {}
    industrial = vector["工业品倾向"] == "是"
    consumer = vector["消费品倾向"] == "是"
    margin = estimated_margin_rate(product)

    for platform in PLATFORM_RULES:
        score = 50
        reasons = []

        if platform == "Amazon":
            if vector["价格带"] in ["中客单价", "高客单价"]:
                score += 15
                reasons.append("客单价具备承接平台佣金和广告测试的空间。")
            if vector["认证数量"] > 0:
                score += 10
                reasons.append("已有认证资料，有利于降低平台审核和准入风险。")
            if product.has_battery or product.is_liquid_or_powder:
                score -= 15
                reasons.append("敏感属性增加审核、物流和合规不确定性。")
            if margin < 0.25:
                score -= 10
                reasons.append("扣费后利润率偏低，Amazon广告测试压力较大。")

        elif platform == "AliExpress":
            if vector["价格带"] in ["低客单价", "中客单价"]:
                score += 15
                reasons.append("价格带适合速卖通快速测品。")
            if vector["物流重量带"] == "轻小件":
                score += 10
                reasons.append("轻小件适合跨境小包履约。")
            if margin < 0.2:
                score -= 8
                reasons.append("利润率偏低，容易陷入价格竞争。")

        elif platform == "TikTok Shop":
            if consumer:
                score += 12
                reasons.append("消费品更适合短视频展示和场景种草。")
            if vector["描述完整度"] == "较完整":
                score += 6
                reasons.append("产品描述较完整，便于生成脚本和卖点素材。")
            if vector["物流重量带"] == "重货/大件":
                score -= 10
                reasons.append("重货不利于内容电商冲动成交和履约成本控制。")
            if product.has_battery:
                score -= 6
                reasons.append("带电产品需要额外核查平台审核、物流和售后条件。")

        elif platform == "独立站":
            if margin >= 0.35:
                score += 15
                reasons.append("利润率具备投流和品牌建设空间。")
            if product.business_goal in ["做品牌", "建渠道"]:
                score += 10
                reasons.append("企业诉求适合沉淀私域和长期品牌资产。")
            if vector["价格带"] == "低客单价":
                score -= 8
                reasons.append("低客单价独立站投流回本压力较大。")

        elif platform == "B2B平台":
            if industrial or product.customer_type == "工厂客户":
                score += 20
                reasons.append("产品具备B端询盘、打样和批量采购逻辑。")
            else:
                score -= 10
                reasons.append("当前产品更接近C端消费品，B2B平台不是第一优先级。")
            if product.business_goal in ["找订单", "建渠道"] and (industrial or product.customer_type == "工厂客户"):
                score += 8
                reasons.append("企业诉求适合B2B获客。")
            if product.customer_type == "C端消费者":
                score -= 15
                reasons.append("目标客户偏C端，B2B推荐权重下调。")

        result[platform] = {
            "匹配分": clamp(score, 0, 100),
            "匹配理由": reasons or ["基础条件一般，建议补充产品资料后再判断。"],
            "适合项": PLATFORM_RULES[platform]["适合"],
            "限制项": PLATFORM_RULES[platform]["限制"],
        }

    return result


def score_market(product: ProductInput, vector: Dict) -> Tuple[int, List[str]]:
    score = 8
    notes = []
    if vector["消费品倾向"] == "是":
        score += 4
        notes.append("产品具备消费场景，适合进行跨境平台测品或内容测试。")
    if vector["工业品倾向"] == "是":
        score += 4
        notes.append("产品具备工业品或供应链属性，适合通过B2B询盘路径验证海外需求。")
    if product.business_goal in ["测品", "找订单", "建渠道"]:
        score += 3
        notes.append("企业诉求与低成本市场验证路径匹配。")
    if contains_any(product.name + product.category, ["手机支架", "数据线", "耳机", "充电器", "水杯", "收纳", "灯具"]):
        score -= 3
        notes.append("产品命中红海关键词，海外需求存在，但必须通过差异化场景、组合套装或内容破局。")
    if product.business_goal == "清库存":
        score -= 2
        notes.append("清库存诉求容易导致价格导向，需防止低价出海、售后失控和品牌损耗。")
    return clamp(score, 0, MAX_SCORES["市场需求适配度"]), notes


def score_platform(platform_match: Dict[str, Dict]) -> Tuple[int, List[str]]:
    best = max(platform_match.items(), key=lambda x: x[1]["匹配分"])
    score = best[1]["匹配分"] / 100 * MAX_SCORES["平台销售适配度"]
    return clamp(score, 0, MAX_SCORES["平台销售适配度"]), [f"当前匹配度最高的平台为 {best[0]}，匹配分为 {best[1]['匹配分']}/100。"]


def score_profit(product: ProductInput) -> Tuple[int, List[str]]:
    margin = estimated_margin_rate(product)
    profit = estimated_single_profit_cny(product)
    notes = [
        f"海外零售价折合人民币约 {retail_price_cny(product)} 元。",
        f"平台佣金估算约 {platform_commission_cny(product)} 元。",
        f"单件利润约 {profit} 元，扣费后利润率约 {margin * 100:.1f}%。",
    ]
    if margin >= 0.45:
        score = 20
        notes.append("利润空间较好，具备平台测试、素材制作和一定广告投入承受力。")
    elif margin >= 0.3:
        score = 16
        notes.append("利润空间尚可，但需要控制广告费和履约成本。")
    elif margin >= 0.18:
        score = 11
        notes.append("利润空间偏紧，只适合小预算验证。")
    elif margin >= 0.05:
        score = 6
        notes.append("利润空间较弱，建议重新核价、优化包装或改走B2B询盘路径。")
    else:
        score = 2
        notes.append("扣费后利润为负或接近为零，暂不建议直接平台化销售。")
    return score, notes


def score_logistics(product: ProductInput, vector: Dict) -> Tuple[int, List[str]]:
    score = 15
    notes = [f"实际重量 {vector['实际重量kg']} kg，体积重 {vector['体积重kg']} kg，计费重量 {vector['计费重量kg']} kg。"]
    if vector["物流重量带"] == "重货/大件":
        score -= 6
        notes.append("计费重量偏高，跨境小包、海外仓和退货成本压力较大。")
    elif vector["物流重量带"] == "中等重量":
        score -= 3
        notes.append("计费重量中等，需要提前测算头程、尾程和仓储成本。")
    else:
        notes.append("轻小件属性较友好，适合小批量跨境测试。")
    if product.has_battery:
        score -= 2
        notes.append("带电属性会增加物流渠道限制和申报要求。")
    if product.has_magnet:
        score -= 1
        notes.append("带磁属性可能影响空运渠道。")
    if product.is_liquid_or_powder:
        score -= 4
        notes.append("液体或粉末类商品物流限制较多。")
    if product.is_fragile:
        score -= 2
        notes.append("易碎属性会增加包装成本、破损率和售后风险。")
    return clamp(score, 0, MAX_SCORES["物流履约适配度"]), notes


def score_compliance(product: ProductInput, vector: Dict) -> Tuple[int, List[str]]:
    score = 8
    notes = []
    certs = normalize_certifications(product.certifications)
    if certs:
        score += min(5, len(certs) * 2)
        notes.append(f"已有认证：{'、'.join(certs)}，有助于降低准入和平台审核风险。")
    else:
        score -= 2
        notes.append("暂无认证资料，需先确认目标市场是否要求 CE、FCC、RoHS、FDA 等认证。")

    if contains_any(product.category + product.name, ["食品", "药品", "医疗", "儿童", "母婴", "化妆品", "电池", "电子", "玩具", "小家电"]):
        score -= 4
        notes.append("类目涉及较高监管敏感度，需提前进行目标国法规和平台禁限售核验。")
    if product.has_battery or product.is_liquid_or_powder:
        score -= 3
        notes.append("产品属性涉及运输和平台审核敏感项，需要补充合规资料。")
    return clamp(score, 0, MAX_SCORES["合规风险可控度"]), notes


def score_content(product: ProductInput, vector: Dict) -> Tuple[int, List[str]]:
    score = 4
    notes = []
    if vector["消费品倾向"] == "是":
        score += 3
        notes.append("产品具备面向C端的展示空间，适合主图、场景图和短视频表达。")
    if vector["描述完整度"] == "较完整":
        score += 2
        notes.append("产品描述较完整，有利于生成 Listing、短视频脚本和卖点图。")
    else:
        notes.append("产品描述偏少，建议补充使用场景、用户痛点和差异化卖点。")
    if product.customer_type == "工厂客户":
        score -= 1
        notes.append("B端工业品更依赖参数、案例和询盘转化，短视频种草权重相对较低。")
    return clamp(score, 0, MAX_SCORES["内容传播适配度"]), notes


def score_competition(product: ProductInput) -> Tuple[int, List[str]]:
    score = 3
    notes = []
    if contains_any(product.name + product.category, ["手机支架", "数据线", "耳机", "充电器", "水杯", "收纳", "灯具"]):
        score -= 2
        notes.append("产品疑似红海类目，需要用差异化卖点、套装、品牌包装或细分场景破局。")
    else:
        score += 1
        notes.append("未命中明显红海关键词，仍需进一步做海外竞品验证。")
    if estimated_margin_rate(product) >= 0.35:
        score += 1
        notes.append("利润率较高，对价格竞争和广告测试有一定承受力。")
    return clamp(score, 0, MAX_SCORES["竞争强度修正值"]), notes


def generate_level(total_score: int) -> str:
    if total_score >= 88:
        return "优先出海测试"
    if total_score >= 72:
        return "适合测试，但需优化资料"
    if total_score >= 58:
        return "谨慎测试，先做小样本验证"
    if total_score >= 42:
        return "不建议直接投入平台运营"
    return "暂不建议跨境电商化"


def generate_decision(product: ProductInput, report: Dict) -> Dict[str, str]:
    score = report["total_score"]
    level = report["level"]
    platforms = "、".join(report["platforms"])
    weak = [k for k, v in report["scores"].items() if v / MAX_SCORES[k] < 0.55]

    if score >= 88:
        decision = "可进入优先测试池"
        investment = "建议进入平台小批量上架与内容测试，投入节奏可适度前置。"
    elif score >= 72:
        decision = "适合测试，但需补齐关键资料"
        investment = "建议先做轻量化测试，不建议一次性重仓广告或备货。"
    elif score >= 58:
        decision = "谨慎测试，先做小样本验证"
        investment = "建议以7天小预算验证为主，先验证点击、询盘、加购和物流可行性。"
    elif score >= 42:
        decision = "暂不建议直接投入平台运营"
        investment = "建议先补齐产品资料、认证、包装、价格模型或渠道路径。"
    else:
        decision = "暂不建议跨境电商化"
        investment = "建议暂缓平台化投入，优先重新评估产品定位和成本结构。"

    return {
        "综合结论": decision,
        "投入建议": investment,
        "优先平台": platforms,
        "主要短板": "、".join(weak) if weak else "暂无明显短板",
        "建议验证周期": "7-14天小样本测试",
        "报告等级": level,
    }


def recommend_platforms(platform_match: Dict[str, Dict]) -> List[str]:
    ranked = sorted(platform_match.items(), key=lambda x: x[1]["匹配分"], reverse=True)
    platforms = []
    for name, data in ranked:
        if name == "B2B平台":
            if data["匹配分"] >= 70:
                platforms.append(name)
        elif data["匹配分"] >= 55:
            platforms.append(name)
        if len(platforms) >= 3:
            break
    return platforms or [ranked[0][0]]


def recommend_markets(product: ProductInput, platforms: List[str]) -> List[str]:
    markets = []
    if "Amazon" in platforms:
        markets.extend(["美国", "欧洲"])
    if "AliExpress" in platforms:
        markets.extend(["欧洲", "拉美", "中东"])
    if "TikTok Shop" in platforms:
        markets.extend(["东南亚", "美国"])
    if "B2B平台" in platforms:
        markets.extend(["欧洲", "中东", "拉美"])
    if "独立站" in platforms:
        markets.extend(["美国", "欧洲"])
    if product.has_battery or product.is_liquid_or_powder:
        markets.append("优先选择物流和清关路径成熟的市场")
    return list(dict.fromkeys(markets)) or ["美国", "欧洲", "东南亚"]


def generate_opc_tasks(product: ProductInput, scores: Dict[str, int], platform_match: Dict[str, Dict]) -> List[Dict[str, str]]:
    tasks = []

    if scores["合规风险可控度"] <= 8:
        tasks.append({"模块": "合规核查", "触发原因": "合规风险偏高", "任务": "核查目标市场认证、平台禁限售、运输申报要求，形成合规资料清单。", "交付物": "合规资料核查表"})
    if scores["物流履约适配度"] <= 10:
        tasks.append({"模块": "物流验证", "触发原因": "物流履约压力", "任务": "向至少3家物流服务商询价，确认可发渠道、计费重量、异常件处理和退货规则。", "交付物": "物流报价与履约风险表"})
    if scores["利润空间适配度"] <= 12:
        tasks.append({"模块": "利润复核", "触发原因": "利润空间偏紧", "任务": "重算价格模型，拆分出厂价、平台佣金、物流费、广告费和售后成本。", "交付物": "单品利润测算表"})
    if scores["内容传播适配度"] <= 6:
        tasks.append({"模块": "内容补强", "触发原因": "内容素材不足", "任务": "补拍产品使用场景素材，提炼用户痛点、差异化卖点和短视频脚本。", "交付物": "素材清单与脚本草案"})
    if scores["竞争强度修正值"] <= 2:
        tasks.append({"模块": "竞争破局", "触发原因": "红海竞争", "任务": "完成差异化竞品分析，围绕场景、人群、套装、包装、价格带设计破局方案。", "交付物": "竞品分析与差异化方案"})

    platforms = recommend_platforms(platform_match)
    tasks.extend([
        {"模块": "平台测试", "触发原因": "平台测试准备", "任务": f"围绕推荐平台（{'、'.join(platforms)}）完成20个海外竞品样本分析。", "交付物": "海外竞品样本表"},
        {"模块": "Listing冷启动", "触发原因": "上架资料准备", "任务": "生成英文标题、五点描述、长描述、搜索关键词和FAQ草稿。", "交付物": "Listing初稿"},
        {"模块": "素材标准化", "触发原因": "销售素材准备", "任务": "整理主图、场景图、尺寸图、卖点图、包装图和工厂资质素材。", "交付物": "跨境素材包"},
        {"模块": "小预算验证", "触发原因": "低成本验证", "任务": "设计7天测品计划，设定曝光、点击、转化、询盘、加购和退款指标。", "交付物": "7天测品计划表"},
        {"模块": "数据回流", "触发原因": "模型优化", "任务": "建立数据复盘表，把测试结果回流到产品适配度评分模型。", "交付物": "数据复盘表"},
    ])
    return tasks


def evaluate_product(product: ProductInput) -> Dict:
    vector = build_feature_vector(product)
    platform_match = match_platform_rules(product, vector)

    market_score, market_notes = score_market(product, vector)
    platform_score, platform_notes = score_platform(platform_match)
    profit_score, profit_notes = score_profit(product)
    logistics_score, logistics_notes = score_logistics(product, vector)
    compliance_score, compliance_notes = score_compliance(product, vector)
    content_score, content_notes = score_content(product, vector)
    competition_score, competition_notes = score_competition(product)

    scores = {
        "市场需求适配度": market_score,
        "平台销售适配度": platform_score,
        "利润空间适配度": profit_score,
        "物流履约适配度": logistics_score,
        "合规风险可控度": compliance_score,
        "内容传播适配度": content_score,
        "竞争强度修正值": competition_score,
    }

    total_score = sum(scores.values())
    platforms = recommend_platforms(platform_match)
    markets = recommend_markets(product, platforms)

    report = {
        "vector": vector,
        "platform_match": platform_match,
        "scores": scores,
        "total_score": total_score,
        "level": generate_level(total_score),
        "platforms": platforms,
        "markets": markets,
        "notes": {
            "市场需求分析": market_notes,
            "平台销售分析": platform_notes,
            "利润空间分析": profit_notes,
            "物流履约分析": logistics_notes,
            "合规风险分析": compliance_notes,
            "内容传播分析": content_notes,
            "竞争强度分析": competition_notes,
        },
    }
    report["decision"] = generate_decision(product, report)
    report["tasks"] = generate_opc_tasks(product, scores, platform_match)
    return report


def risk_level(score: int, max_score: int) -> str:
    ratio = score / max_score
    if ratio >= 0.75:
        return "低风险"
    if ratio >= 0.55:
        return "中风险"
    return "高风险"


def generate_report_no(product: ProductInput) -> str:
    clean_name = "".join([c for c in product.name if c.isalnum()])[:8] or "PRODUCT"
    return f"XH-CB-{datetime.now().strftime('%Y%m%d%H%M')}-{clean_name}"


def generate_markdown_report(product: ProductInput, report: Dict) -> str:
    no = generate_report_no(product)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    decision = report["decision"]
    vector = report["vector"]

    lines = []
    lines.append(f"# 星狐AI跨境商品诊断舱｜产品适配度诊断报告\n")
    lines.append(f"**报告编号：** {no}  ")
    lines.append(f"**生成时间：** {now}  ")
    lines.append(f"**诊断对象：** {product.name}  ")
    lines.append(f"**报告版本：** Demo v5｜外部演示版\n")
    lines.append("> 说明：本报告基于产品基础信息、价格口径、物流约束、合规资料、平台适配规则和内容传播条件生成，用于跨境电商前期决策、产品测品准备和OPC任务拆解参考。\n")

    lines.append("---\n")
    lines.append("## 一、执行摘要")
    lines.append(f"- **综合评分：** {report['total_score']} / 100")
    lines.append(f"- **诊断等级：** {report['level']}")
    lines.append(f"- **综合结论：** {decision['综合结论']}")
    lines.append(f"- **投入建议：** {decision['投入建议']}")
    lines.append(f"- **推荐平台：** {'、'.join(report['platforms'])}")
    lines.append(f"- **推荐市场：** {'、'.join(report['markets'])}")
    lines.append(f"- **主要短板：** {decision['主要短板']}")
    lines.append(f"- **建议验证周期：** {decision['建议验证周期']}\n")

    lines.append("## 二、产品基础画像")
    lines.append("| 指标 | 结果 |")
    lines.append("|---|---|")
    for key in ["产品类型判定", "价格带", "客户类型", "企业诉求", "已有认证", "物流敏感属性", "描述完整度"]:
        lines.append(f"| {key} | {vector[key]} |")
    lines.append("")

    lines.append("## 三、经营测算模型")
    lines.append("| 项目 | 数值 |")
    lines.append("|---|---:|")
    lines.append(f"| 海外零售价（折人民币） | {vector['海外零售价人民币口径']} 元 |")
    lines.append(f"| 出厂价 | {vector['出厂价']} 元 |")
    lines.append(f"| 平台佣金估算 | {vector['估算平台佣金']} 元 |")
    lines.append(f"| 单件物流费估算 | {vector['估算单件物流费']} 元 |")
    lines.append(f"| 扣费后单件利润 | {vector['估算单件利润']} 元 |")
    lines.append(f"| 扣费后利润率 | {vector['扣费后利润率'] * 100:.1f}% |")
    lines.append(f"| 单件最大可承受广告成本 | {vector['单件最大可承受广告成本']} 元 |\n")

    lines.append("## 四、七维评分矩阵")
    lines.append("| 评估维度 | 得分 | 满分 | 风险等级 |")
    lines.append("|---|---:|---:|---|")
    for k, v in report["scores"].items():
        lines.append(f"| {k} | {v} | {MAX_SCORES[k]} | {risk_level(v, MAX_SCORES[k])} |")
    lines.append("")

    lines.append("## 五、平台适配与渠道建议")
    lines.append("| 平台 | 匹配分 | 判断说明 |")
    lines.append("|---|---:|---|")
    for platform, data in report["platform_match"].items():
        lines.append(f"| {platform} | {data['匹配分']}/100 | {'；'.join(data['匹配理由'])} |")
    lines.append("")

    lines.append("## 六、风险提示与补强方向")
    for title, notes in report["notes"].items():
        lines.append(f"### {title}")
        for note in notes:
            lines.append(f"- {note}")
        lines.append("")

    lines.append("## 七、OPC运营任务拆解")
    lines.append("| 序号 | 模块 | 触发原因 | 任务内容 | 交付物 |")
    lines.append("|---:|---|---|---|---|")
    for i, task in enumerate(report["tasks"], start=1):
        lines.append(f"| {i} | {task['模块']} | {task['触发原因']} | {task['任务']} | {task['交付物']} |")
    lines.append("")

    lines.append("## 八、7天小样本验证路径")
    lines.append("| 阶段 | 时间 | 核心动作 | 输出结果 |")
    lines.append("|---|---|---|---|")
    lines.append("| 准备期 | D1-D2 | 补齐认证、物流、竞品、素材和Listing草稿 | 测试准备包 |")
    lines.append("| 上架期 | D3 | 完成平台测试页面或询盘页搭建 | 初始测试链接 |")
    lines.append("| 测试期 | D4-D6 | 低预算投放或自然流量测试，记录曝光、点击、加购、询盘 | 测试数据表 |")
    lines.append("| 复盘期 | D7 | 复盘利润、物流、内容、平台匹配与OPC执行质量 | 复盘报告与下一步建议 |\n")

    lines.append("## 九、数据回流字段")
    lines.append("建议后续将曝光量、点击率、加购率、转化率、询盘数、退款率、物流异常率、广告消耗、实际利润、企业满意度、OPC交付质量等数据回流至评分模型，用于持续优化产品适配度判断。\n")

    lines.append("## 十、技术链路")
    lines.append("产品数据采集 → 标准化处理 → 产品特征向量生成 → 平台规则匹配 → 多维权重评分 → 风险提示 → OPC任务生成 → 数据回流\n")

    lines.append("---")
    lines.append("**保密提示：** 本报告为系统自动生成的演示版诊断结果，仅供产品出海前期决策参考，不构成最终经营承诺或法律、税务、合规意见。")
    return "\n".join(lines)


def render_tags(items: List[str], style: str = ""):
    html = "".join([f'<span class="tag {style}">{item}</span>' for item in items])
    st.markdown(html, unsafe_allow_html=True)


def render_metric(label: str, value: str, sub: str = ""):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_sample(sample_name: str):
    if sample_name not in SAMPLE_CASES:
        return
    sample = SAMPLE_CASES[sample_name]
    for k, v in sample.items():
        st.session_state[k] = v


def get_diagnosis_client() -> DiagnosisApiClient:
    return DiagnosisApiClient()


def _remember_uploaded_file(uploaded):
    if uploaded is None:
        return
    content = uploaded.getvalue()
    if not content:
        return
    if len(content) > 5 * 1024 * 1024:
        st.warning(f"{uploaded.name} 超过 5 MiB，未加入图片证据。")
        return
    media_type = getattr(uploaded, "type", "")
    if media_type not in {"image/jpeg", "image/png", "image/webp"}:
        st.warning(f"{uploaded.name} 不是支持的 JPEG / PNG / WebP 图片。")
        return
    digest = hashlib.sha256(content).hexdigest()
    assets = st.session_state.setdefault("image_assets", {})
    if digest not in st.session_state.setdefault("deleted_image_hashes", set()) and len(assets) < 4:
        assets[digest] = ImageAsset(uploaded.name, media_type, content)


def render_image_workspace(client: DiagnosisApiClient):
    with st.expander("产品图片识别与证据建议", expanded=True):
        st.markdown(
            '<div class="evidence-shell"><div class="evidence-kicker">PHOTO → EVIDENCE</div><div class="evidence-title">先看图，再由你确认产品事实</div><div class="evidence-note">最多 4 张，每张不超过 5 MiB。图片只生成建议，不会覆盖手工字段；认证、价格、规格和敏感属性缺少证据时必须保持未知。</div></div>',
            unsafe_allow_html=True,
        )
        upload_col, camera_col = st.columns(2)
        with upload_col:
            uploads = st.file_uploader("上传产品图", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, key="product_photo_uploads")
            for uploaded in uploads or []:
                _remember_uploaded_file(uploaded)
        with camera_col:
            camera = st.camera_input("现场拍摄", key="product_camera")
            _remember_uploaded_file(camera)

        assets = st.session_state.setdefault("image_assets", {})
        if assets:
            st.caption(f"已进入本次诊断证据区：{len(assets)} / 4 张")
            cols = st.columns(min(4, len(assets)))
            for index, (digest, asset) in enumerate(list(assets.items())):
                with cols[index % len(cols)]:
                    st.image(asset.content, caption=asset.filename, width="stretch")
                    if st.button("移除", key=f"remove_image_{digest}", width="stretch"):
                        assets.pop(digest, None)
                        st.session_state["deleted_image_hashes"].add(digest)
                        st.session_state.pop("extraction_result", None)
                        st.session_state.pop("extraction_draft", None)
                        st.rerun()

            context = st.text_input("给识别的补充线索（可选）", placeholder="例如：这是用于 CNC 加工的刀具，不确定具体材质", key="image_context")
            if st.button("识别图片并生成待确认建议", type="primary", width="stretch", disabled=not client.configured):
                idempotency = "ui-extract-" + hashlib.sha256(("".join(sorted(assets)) + context).encode()).hexdigest()[:32]
                try:
                    with st.spinner("正在核验图片并提取可见证据…"):
                        result = client.extract(idempotency, assets.values(), context)
                    st.session_state["extraction_result"] = result["suggestions"]
                    st.session_state["extraction_draft"] = {"draftId": result["draftId"], "accessToken": result["accessToken"]}
                except DiagnosisApiError as exc:
                    st.error(str(exc))
            if not client.configured:
                st.info("图片可继续预览并随手工资料进入 v5 报告；融合诊断服务配置完成后，这里会出现结构化识别建议。")
        else:
            st.caption("也可以完全不上传图片，继续使用原有样本或手工输入流程。")

        extraction = st.session_state.get("extraction_result")
        if extraction:
            suggestions = extraction.get("suggestions", [])
            st.markdown("#### 待确认建议")
            if suggestions:
                selected = []
                for index, suggestion in enumerate(suggestions):
                    label = f"{suggestion.get('field', '字段')} → {suggestion.get('value', '')}（置信度 {suggestion.get('confidence', 0) * 100:.0f}%）"
                    if st.checkbox(label, key=f"accept_suggestion_{index}"):
                        selected.append(suggestion)
                    st.caption(f"图片证据：{suggestion.get('evidence', '未说明')}。勾选后仍可在表单中修改。")
                if st.button("应用已勾选建议", width="stretch"):
                    applied = apply_selected_suggestions(selected)
                    st.success(f"已应用 {applied} 项；请继续在标准档案中核对。")
                    st.rerun()
            else:
                st.warning("图片中没有足够可验证的信息可安全写入字段，请以实物资料或人工输入为准。")
            for warning in extraction.get("warnings", []):
                st.caption(f"⚠ {warning}")
            if extraction.get("missingInformation"):
                st.caption("仍需补充：" + "、".join(extraction["missingInformation"]))


def apply_selected_suggestions(suggestions: List[Dict]) -> int:
    field_map = {
        "name": "name", "category": "category", "material": "material", "description": "product_description",
        "factoryPriceCny": "factory_price_cny", "retailPriceUsd": "retail_price_usd", "weightG": "weight_g",
        "lengthCm": "length_cm", "widthCm": "width_cm", "heightCm": "height_cm", "hasBattery": "has_battery",
        "hasMagnet": "has_magnet", "isLiquidOrPowder": "is_liquid_or_powder", "isFragile": "is_fragile",
        "certifications": "certifications",
    }
    applied_values = st.session_state.setdefault("image_applied_values", {})
    count = 0
    for suggestion in suggestions:
        canonical = suggestion.get("field")
        widget = field_map.get(canonical)
        if not widget:
            continue
        value = suggestion.get("value")
        if widget in {"factory_price_cny", "retail_price_usd", "weight_g", "length_cm", "width_cm", "height_cm"}:
            value = str(value)
        st.session_state[widget] = value
        applied_values[canonical] = value
        count += 1
    return count


def parse_list_text(value: str) -> List[str]:
    return [item.strip() for item in value.replace("，", ",").replace("\n", ",").split(",") if item.strip()]


def optional_float(value):
    text = str(value or "").strip().replace("，", ".").replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def optional_bool(value):
    return True if value == "是" else False if value == "否" else None


def build_canonical_product(product: ProductInput, extras: Dict[str, str], report: Dict) -> Dict:
    product_type = report["vector"]["产品类型判定"]
    product_class = "industrial" if "B端工业" in product_type else "consumer" if "C端消费" in product_type else "hybrid" if "混合" in product_type else "unknown"
    extraction = st.session_state.get("extraction_result", {})
    missing = parse_list_text(extras.get("missing_information", ""))
    missing.extend(extraction.get("missingInformation", []))
    values = {
        "name": product.name, "category": product.category, "description": product.product_description, "material": product.material,
        "factoryPriceCny": product.factory_price_cny, "retailPriceUsd": product.retail_price_usd, "exchangeRate": product.exchange_rate,
        "platformCommissionRate": product.platform_commission_rate, "estimatedLogisticsCny": product.estimated_logistics_cny,
        "weightG": product.weight_g, "lengthCm": product.length_cm, "widthCm": product.width_cm, "heightCm": product.height_cm,
        "hasBattery": product.has_battery, "hasMagnet": product.has_magnet, "isLiquidOrPowder": product.is_liquid_or_powder,
        "isFragile": product.is_fragile, "certifications": normalize_certifications(product.certifications),
        "customerType": product.customer_type, "businessGoal": product.business_goal,
    }
    applied = st.session_state.get("image_applied_values", {})
    evidence = {}
    for field, value in values.items():
        from_image = field in applied and str(applied[field]) == str(value)
        evidence[field] = {"source": "image" if from_image else "user", "confidence": 0.7 if from_image else 1.0, **({"reference": "image:confirmed"} if from_image else {})}
    return {
        **values,
        "aliases": parse_list_text(extras.get("aliases", "")),
        "productClass": product_class,
        "specifications": parse_list_text(extras.get("specifications", "")),
        "useScenarios": parse_list_text(extras.get("use_scenarios", "")),
        "purchaserRoles": parse_list_text(extras.get("purchaser_roles", "")),
        "userRoles": parse_list_text(extras.get("user_roles", "")),
        "missingInformation": list(dict.fromkeys(missing))[:30],
        "intendedMarkets": parse_list_text(extras.get("intended_markets", "")),
        "intendedChannels": parse_list_text(extras.get("intended_channels", "")),
        "advertisingAllowanceCny": optional_float(extras.get("advertising_allowance", "")),
        "returnAfterSalesReserveCny": optional_float(extras.get("return_reserve", "")),
        "marketDemandEvidence": parse_list_text(extras.get("market_demand_evidence", "")),
        "competitorEvidence": parse_list_text(extras.get("competitor_evidence", "")),
        "moqUnits": optional_float(extras.get("moq_units", "")),
        "monthlyCapacityUnits": optional_float(extras.get("monthly_capacity", "")),
        "leadTimeDays": optional_float(extras.get("lead_time_days", "")),
        "qualityControlReady": optional_bool(extras.get("quality_control_ready", "未知")),
        "localizedContentReady": optional_bool(extras.get("localized_content_ready", "未知")),
        "operationsOwnerReady": optional_bool(extras.get("operations_owner_ready", "未知")),
        "validationBudgetCny": optional_float(extras.get("validation_budget", "")),
        "validationWindowDays": optional_float(extras.get("validation_window_days", "")),
        "fieldEvidence": evidence,
    }


def start_remote_diagnosis(client: DiagnosisApiClient, canonical: Dict):
    if not client.configured:
        return
    pending_key = st.session_state.setdefault("pending_diagnosis_key", f"ui-diag-{uuid4()}")
    draft = st.session_state.get("extraction_draft")
    assets = st.session_state.get("image_assets", {}).values()
    try:
        result = client.create(pending_key, canonical, assets, draft.get("draftId") if draft else None, draft.get("accessToken") if draft else None)
        st.session_state["diagnosis_handle"] = {"diagnosisId": result["diagnosisId"], "accessToken": result["accessToken"]}
        st.session_state["just_started_diagnosis"] = True
        st.session_state.pop("pending_diagnosis_key", None)
    except DiagnosisApiError as exc:
        st.warning(f"v5 报告已生成；融合诊断将在服务恢复后使用同一幂等任务继续：{exc}")


def render_diagnosis_reloader(client: DiagnosisApiClient):
    with st.sidebar.expander("重新打开已保存报告"):
        recovery = st.text_input("报告恢复码", type="password", help="恢复码只用于服务端读取已保存快照，不会重新运行分析。")
        if st.button("载入报告", width="stretch"):
            try:
                diagnosis_id, token = recovery.strip().split(":", 1)
                result = client.result(diagnosis_id, token)
                st.session_state["diagnosis_handle"] = {"diagnosisId": diagnosis_id, "accessToken": token}
                st.session_state["fused_result"] = result
                restore_local_v5_context(result.get("report", {}))
                st.success("报告已从持久化快照载入。")
            except (ValueError, DiagnosisApiError):
                st.error("恢复码无效或报告尚未完成。")


def refresh_remote_diagnosis(client: DiagnosisApiClient):
    handle = st.session_state.get("diagnosis_handle")
    if not handle or not client.configured:
        return
    diagnosis_id, token = handle["diagnosisId"], handle["accessToken"]
    progress = st.progress(0, text="正在读取诊断进度…")
    iterations = 40 if st.session_state.pop("just_started_diagnosis", False) else 1
    try:
        for _ in range(iterations):
            status = client.status(diagnosis_id, token)
            progress.progress(status["progressPercent"] / 100, text=status["events"][-1]["publicMessage"] if status.get("events") else "任务已接收")
            if status["status"] == "SUCCEEDED":
                st.session_state["fused_result"] = client.result(diagnosis_id, token)
                break
            if status["status"] == "FAILED":
                st.warning("融合诊断未完成；资料与进度已保存，可稍后用恢复码重试查看。")
                break
            time.sleep(0.5)
        if status["status"] not in {"SUCCEEDED", "FAILED"} and st.button("刷新融合进度", width="stretch"):
            st.rerun()
        st.caption("报告恢复码（请自行妥善保存）")
        st.code(f"{diagnosis_id}:{token}", language=None)
    except DiagnosisApiError as exc:
        st.warning(str(exc))


def claim_card(claim: Dict, style: str = ""):
    labels = {"evidence": "证据", "inference": "推断", "unknown": "未知", "recommendation": "建议"}
    kind = claim.get("kind", "unknown")
    refs = "".join(f'<span class="source-chip evidence">{html.escape(str(ref))}</span>' for ref in claim.get("evidenceRefs", [])[:4])
    st.markdown(
        f'<div class="claim-card {style}"><span class="source-chip {kind}">{labels.get(kind, "未知")}</span><strong>{html.escape(str(claim.get("topic", "判断")))}</strong><div>{html.escape(str(claim.get("statement", "")))}</div><div class="claim-meta">置信度 {float(claim.get("confidence", 0)) * 100:.0f}% · {html.escape(str(claim.get("rationale", "")))}</div><div>{refs}</div></div>',
        unsafe_allow_html=True,
    )


def render_fused_report(client: DiagnosisApiClient):
    result = st.session_state.get("fused_result")
    if not result:
        return
    report = result.get("report", {})
    st.markdown("### 4. 多源融合增量报告")
    confidence = report.get("confidence", {})
    st.markdown(
        f'<div class="evidence-shell"><div class="evidence-kicker">FUSED COMMERCIAL BRIEF</div><div class="evidence-title">共识保留，冲突可见，未知不补写</div><div class="evidence-note">总置信度 {float(confidence.get("overall", 0)) * 100:.0f}% · {html.escape(str(confidence.get("method", "")))}</div></div>',
        unsafe_allow_html=True,
    )
    groups = [("机会判断", report.get("opportunity", [])), ("目标市场", report.get("targetMarkets", [])), ("渠道适配", report.get("channelFit", [])), ("下一步行动", report.get("nextActions", []))]
    for title, claims in groups:
        if claims:
            st.markdown(f"#### {title}")
            for claim in claims:
                claim_card(claim)
    red = report.get("risks", {}).get("red", [])
    yellow = report.get("risks", {}).get("yellow", [])
    if red or yellow:
        st.markdown("#### 红 / 黄风险")
        r1, r2 = st.columns(2)
        with r1:
            st.markdown("**红色｜先处理再投入**")
            for claim in red:
                claim_card(claim, "risk-red")
        with r2:
            st.markdown("**黄色｜边验证边补证据**")
            for claim in yellow:
                claim_card(claim, "risk-yellow")
    if report.get("disagreements"):
        st.markdown("#### 分歧与不确定性")
        for disagreement in report["disagreements"]:
            with st.expander(disagreement.get("topic", "分析分歧")):
                for position in disagreement.get("positions", []):
                    st.write(f"- {position.get('source', '独立分析')}：{position.get('statement', '')}")
                st.caption(disagreement.get("resolution", ""))
    if report.get("missingEvidence"):
        st.markdown("#### 尚缺证据")
        render_tags(report["missingEvidence"], "risk")

    with st.expander("本次融合快照包含的 v5 完整交付结构"):
        st.write("执行摘要、产品画像、经营测算、七维评分、平台分析、风险、OPC任务、7天验证路径、数据回流字段与技术链路均已写入不可变报告版本。页面上方继续保留原 v5 的逐项展示与下载。")

    with st.form("diagnosis_feedback_form"):
        st.markdown("#### 这份报告是否有用、准确？")
        usefulness = st.slider("实用性", 1, 5, 4)
        accuracy = st.slider("准确性", 1, 5, 4)
        comment = st.text_area("补充反馈（可选）", max_chars=1000)
        if st.form_submit_button("提交报告反馈", width="stretch"):
            try:
                handle = st.session_state["diagnosis_handle"]
                client.feedback(handle["diagnosisId"], handle["accessToken"], usefulness, accuracy, comment)
                st.success("反馈已保存，将用于后续评估。")
            except DiagnosisApiError as exc:
                st.error(str(exc))

    with st.expander("稍后回填真实结果"):
        with st.form("diagnosis_outcome_form"):
            inquiries = st.number_input("实际询盘数", min_value=0, step=1)
            actual_profit = st.number_input("实际利润（人民币，可为负）", step=1.0)
            outcome_notes = st.text_area("结果说明", max_chars=2000)
            if st.form_submit_button("保存结果反馈", width="stretch"):
                try:
                    handle = st.session_state["diagnosis_handle"]
                    client.outcome(handle["diagnosisId"], handle["accessToken"], datetime.now().astimezone().isoformat(), {"inquiries": inquiries, "actualProfitCny": actual_profit}, outcome_notes)
                    st.success("结果反馈已保存，无需重新运行诊断。")
                except DiagnosisApiError as exc:
                    st.error(str(exc))


def legacy_main():
    st.set_page_config(page_title="星狐AI跨境商品诊断舱 Demo", page_icon="🦊", layout="wide")
    st.markdown('<meta name="google" content="notranslate">', unsafe_allow_html=True)
    load_css()
    diagnosis_client = get_diagnosis_client()
    render_diagnosis_reloader(diagnosis_client)

    st.markdown(
        """
        <div class="hero notranslate">
            <div class="pill">AI + 跨境电商 · 产品出海前置诊断 Demo v5</div>
            <h1>星狐AI跨境商品诊断舱</h1>
            <p>输入一个制造业产品，系统自动完成特征识别、平台匹配、利润测算、风险提示、OPC任务拆解与交付型诊断报告生成。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("快速载入演示案例", expanded=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            sample_choice = st.selectbox(
                "选择一个演示样本",
                ["不使用样本，手动填写"] + list(SAMPLE_CASES.keys()),
                help="用于现场演示三类典型产品：C端红海、B端工业品、带电小家电。"
            )
        with c2:
            st.write("")
            st.write("")
            if st.button("载入所选样本", width="stretch"):
                if sample_choice != "不使用样本，手动填写":
                    apply_sample(sample_choice)
                    st.success("样本已载入，可直接点击生成诊断报告。")
                    st.rerun()

    render_image_workspace(diagnosis_client)

    left, right = st.columns([1.15, 0.85], gap="large")

    with left:
        with st.form("demo_form"):
            st.markdown('<div class="small-title">一、产品信息录入</div>', unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                name = st.text_input("产品名称 *", placeholder="例如：硬质合金铣刀 / 便携式迷你吸尘器", key="name")
                category = st.text_input("产品类目 *", placeholder="例如：工业刀具 / 小家电 / 汽配", key="category")
                factory_price_cny = st.text_input("出厂价（人民币）*", placeholder="例如：45", key="factory_price_cny")
                retail_price_usd = st.text_input("建议海外零售价（美元）*", placeholder="例如：29.99", key="retail_price_usd")
                exchange_rate = st.text_input("汇率（美元兑人民币）*", placeholder="例如：7.2", key="exchange_rate")
                platform_commission_rate = st.text_input("平台佣金率 *", placeholder="例如：0.15", key="platform_commission_rate")

            with c2:
                estimated_logistics_cny = st.text_input("估算单件物流费（人民币）*", placeholder="例如：18", key="estimated_logistics_cny")
                weight_g = st.text_input("产品重量（g）*", placeholder="例如：850", key="weight_g")
                length_cm = st.text_input("包装长度（cm）*", placeholder="例如：25", key="length_cm")
                width_cm = st.text_input("包装宽度（cm）*", placeholder="例如：15", key="width_cm")
                height_cm = st.text_input("包装高度（cm）*", placeholder="例如：12", key="height_cm")
                material = st.text_input("产品材质", placeholder="例如：ABS塑料 / 钨钢 / 铝合金", key="material")

            st.markdown("**产品特殊属性**")
            a, b, c, d = st.columns(4)
            with a:
                has_battery = st.checkbox("带电", key="has_battery")
            with b:
                has_magnet = st.checkbox("带磁", key="has_magnet")
            with c:
                is_liquid_or_powder = st.checkbox("液体/粉末", key="is_liquid_or_powder")
            with d:
                is_fragile = st.checkbox("易碎", key="is_fragile")

            c3, c4 = st.columns(2)
            with c3:
                certifications = st.multiselect(
                    "已有认证",
                    ["无", "CE", "FCC", "RoHS", "FDA", "UKCA", "UL", "REACH"],
                    key="certifications",
                    placeholder="请选择已有认证"
                )
                customer_type = st.selectbox("目标客户类型 *", ["请选择", "C端消费者", "小B商家", "工厂客户"], key="customer_type")
            with c4:
                business_goal = st.selectbox("企业诉求 *", ["请选择", "测品", "找订单", "做品牌", "清库存", "建渠道"], key="business_goal")

            product_description = st.text_area(
                "产品描述 / 使用场景 / 核心卖点",
                placeholder="请简单描述产品用途、目标客户、使用场景、核心卖点。信息越完整，诊断越准确。",
                key="product_description",
                height=116
            )

            with st.expander("补充标准产品档案（可选）"):
                st.caption("图片和文字最终汇合到同一份可修订档案；以下内容不会改变原 v5 计算公式。")
                e1, e2 = st.columns(2)
                with e1:
                    aliases = st.text_input("产品别名", placeholder="多个别名用逗号分隔", key="canonical_aliases")
                    specifications = st.text_area("规格参数", placeholder="例如：直径6mm, 四刃, 总长50mm", key="canonical_specifications", height=80)
                    use_scenarios = st.text_input("使用场景", placeholder="例如：CNC加工, 模具加工", key="canonical_use_scenarios")
                    purchaser_roles = st.text_input("采购角色", placeholder="例如：工厂采购, 经销商", key="canonical_purchaser_roles")
                with e2:
                    user_roles = st.text_input("实际使用者", placeholder="例如：机加工操作员", key="canonical_user_roles")
                    intended_markets = st.text_input("意向市场", placeholder="例如：德国, 美国", key="canonical_intended_markets")
                    intended_channels = st.text_input("意向渠道", placeholder="例如：B2B平台, 独立站", key="canonical_intended_channels")
                    missing_information = st.text_area("仍不确定 / 待补证据", placeholder="例如：目标国认证要求, 实际运价", key="canonical_missing_information", height=80)

            submitted = st.form_submit_button("生成诊断报告", width="stretch")

    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="small-title">Demo输出内容</div>', unsafe_allow_html=True)
        st.write("系统将生成一份可交付型诊断报告，包含：")
        render_tags(["执行摘要", "产品画像", "经营测算"], "ok")
        render_tags(["平台匹配", "七维评分", "风险矩阵"])
        render_tags(["OPC任务拆解", "7天验证路径", "数据回流字段"], "dark")
        st.markdown('<div class="footer-note">演示建议：先选一个样本直接跑，再手动修改价格、物流费或认证状态，观察系统结论变化。</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if submitted:
        errors = []
        if not name.strip():
            errors.append("产品名称不能为空。")
        if not category.strip():
            errors.append("产品类目不能为空。")
        if customer_type == "请选择":
            errors.append("请选择目标客户类型。")
        if business_goal == "请选择":
            errors.append("请选择企业诉求。")

        factory_price = parse_float("出厂价", factory_price_cny, errors)
        retail_price = parse_float("建议海外零售价", retail_price_usd, errors)
        rate = parse_float("汇率", exchange_rate, errors, min_value=0.1)
        commission = parse_float("平台佣金率", platform_commission_rate, errors, min_value=0.0)
        logistics = parse_float("估算单件物流费", estimated_logistics_cny, errors)
        weight = parse_float("产品重量", weight_g, errors)
        length = parse_float("包装长度", length_cm, errors)
        width = parse_float("包装宽度", width_cm, errors)
        height = parse_float("包装高度", height_cm, errors)

        if commission > 0.5:
            errors.append("平台佣金率建议填写0到0.5之间，例如0.15。")

        if errors:
            st.error("请先修正以下信息：")
            for error in errors:
                st.write(f"- {error}")
            return

        product = ProductInput(
            name=name.strip(),
            category=category.strip(),
            factory_price_cny=factory_price,
            retail_price_usd=retail_price,
            exchange_rate=rate,
            platform_commission_rate=commission,
            estimated_logistics_cny=logistics,
            weight_g=weight,
            length_cm=length,
            width_cm=width,
            height_cm=height,
            material=material.strip() or "未填写",
            has_battery=has_battery,
            has_magnet=has_magnet,
            is_liquid_or_powder=is_liquid_or_powder,
            is_fragile=is_fragile,
            certifications=certifications or ["无"],
            customer_type=customer_type,
            business_goal=business_goal,
            product_description=product_description.strip(),
        )

        st.session_state["report"] = evaluate_product(product)
        st.session_state["product"] = product
        extras = {
            "aliases": aliases, "specifications": specifications, "use_scenarios": use_scenarios,
            "purchaser_roles": purchaser_roles, "user_roles": user_roles, "intended_markets": intended_markets,
            "intended_channels": intended_channels, "missing_information": missing_information,
        }
        canonical = build_canonical_product(product, extras, st.session_state["report"])
        st.session_state["canonical_product"] = canonical
        start_remote_diagnosis(diagnosis_client, canonical)

    refresh_remote_diagnosis(diagnosis_client)

    if "report" in st.session_state and "product" in st.session_state:
        report = st.session_state["report"]
        product = st.session_state["product"]
        decision = report["decision"]

        st.markdown("---")
        st.markdown(
            f"""
            <div class="report-title">
                <h2>二、产品适配度诊断报告</h2>
                <p>诊断对象：{product.name} ｜ 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} ｜ 报告版本：Demo v5</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            render_metric("跨境适配度总分", f"{report['total_score']}/100", decision["综合结论"])
        with m2:
            render_metric("诊断等级", report["level"], "系统结论")
        with m3:
            render_metric("计费重量", f"{report['vector']['计费重量kg']} kg", report["vector"]["物流重量带"])
        with m4:
            render_metric("扣费后利润率", f"{report['vector']['扣费后利润率'] * 100:.1f}%", f"单件利润 {report['vector']['估算单件利润']} 元")

        st.markdown("### 1. 执行摘要")
        summary_rows = [
            {"项目": "综合结论", "内容": decision["综合结论"]},
            {"项目": "投入建议", "内容": decision["投入建议"]},
            {"项目": "推荐平台", "内容": "、".join(report["platforms"])},
            {"项目": "推荐市场", "内容": "、".join(report["markets"])},
            {"项目": "主要短板", "内容": decision["主要短板"]},
            {"项目": "建议验证周期", "内容": decision["建议验证周期"]},
        ]
        st.table(summary_rows)

        st.markdown("### 2. 七维评分矩阵")
        score_rows = []
        for dimension, score in report["scores"].items():
            score_rows.append({
                "评估维度": dimension,
                "得分": score,
                "满分": MAX_SCORES[dimension],
                "风险等级": risk_level(score, MAX_SCORES[dimension]),
            })
            st.write(f"**{dimension}：{score} / {MAX_SCORES[dimension]}**")
            st.progress(score / MAX_SCORES[dimension])
        st.table(score_rows)

        tab1, tab2, tab3, tab4, tab5 = st.tabs(["产品画像", "经营测算", "平台匹配", "风险说明", "OPC任务与验证路径"])

        with tab1:
            rows = [{"特征项": k, "识别结果": str(v)} for k, v in report["vector"].items()]
            st.table(rows)

        with tab2:
            finance_rows = [
                {"项目": "海外零售价折人民币", "数值": f"{report['vector']['海外零售价人民币口径']} 元"},
                {"项目": "出厂价", "数值": f"{report['vector']['出厂价']} 元"},
                {"项目": "平台佣金估算", "数值": f"{report['vector']['估算平台佣金']} 元"},
                {"项目": "单件物流费估算", "数值": f"{report['vector']['估算单件物流费']} 元"},
                {"项目": "扣费后单件利润", "数值": f"{report['vector']['估算单件利润']} 元"},
                {"项目": "扣费后利润率", "数值": f"{report['vector']['扣费后利润率'] * 100:.1f}%"},
                {"项目": "单件最大可承受广告成本", "数值": f"{report['vector']['单件最大可承受广告成本']} 元"},
            ]
            st.table(finance_rows)

        with tab3:
            for platform, data in report["platform_match"].items():
                with st.expander(f"{platform}｜匹配分 {data['匹配分']} / 100", expanded=False):
                    st.write("**匹配理由**")
                    for reason in data["匹配理由"]:
                        st.write(f"- {reason}")
                    st.write("**适合项**")
                    render_tags(data["适合项"], "ok")
                    st.write("**限制项**")
                    render_tags(data["限制项"], "risk")

        with tab4:
            for title, notes in report["notes"].items():
                with st.expander(title, expanded=True):
                    for note in notes:
                        st.write(f"- {note}")

        with tab5:
            task_rows = []
            for i, task in enumerate(report["tasks"], start=1):
                task_rows.append({
                    "序号": i,
                    "模块": task["模块"],
                    "触发原因": task["触发原因"],
                    "任务内容": task["任务"],
                    "交付物": task["交付物"],
                })
            st.table(task_rows)

            st.markdown("#### 7天小样本验证路径")
            st.table([
                {"阶段": "准备期", "时间": "D1-D2", "核心动作": "补齐认证、物流、竞品、素材和Listing草稿", "输出结果": "测试准备包"},
                {"阶段": "上架期", "时间": "D3", "核心动作": "完成平台测试页面或询盘页搭建", "输出结果": "初始测试链接"},
                {"阶段": "测试期", "时间": "D4-D6", "核心动作": "低预算投放或自然流量测试，记录曝光、点击、加购、询盘", "输出结果": "测试数据表"},
                {"阶段": "复盘期", "时间": "D7", "核心动作": "复盘利润、物流、内容、平台匹配与OPC执行质量", "输出结果": "复盘报告与下一步建议"},
            ])

        st.markdown("### 3. 导出交付型诊断报告")
        md = generate_markdown_report(product, report)
        st.download_button(
            label="下载完整诊断报告",
            data=md,
            file_name=f"{product.name}_跨境电商适配度诊断报告.md",
            mime="text/markdown",
            width="stretch",
        )

        st.markdown(
            """
            <div class="footer-note">
            专利样机技术链路：产品数据采集 → 标准化处理 → 产品特征向量生成 → 平台规则匹配 → 多维权重评分 → 风险提示 → OPC任务生成 → 数据回流。
            </div>
            """,
            unsafe_allow_html=True,
        )

    render_fused_report(diagnosis_client)


def sample_v2_report():
    module_ids = [
        "demand_signal", "customer_chain", "market_fit", "channel_fit", "competition", "unit_economics",
        "logistics", "compliance", "supply_chain", "content_readiness", "operational_readiness", "validation_feasibility",
    ]
    modules = [{
        "id": module_id, "label": f"决策模块 {index + 1}", "score": 60 + index, "weight": 8,
        "confidence": .65, "evidenceRefs": ["input:confirmed"], "inferences": ["待验证推断"], "unknowns": [],
        "positiveDrivers": ["已有用户确认输入"], "lostScoreDrivers": ["真实市场数据待补"],
        "improvementLevers": ["完成小样本验证"], "nextValidationQuestion": "是否达到目标行动？",
        "validationThreshold": "7天内至少3个目标行动", "causalChain": ["输入", "规则", "决策"],
    } for index, module_id in enumerate(module_ids)]
    cards = [{"id": f"card-{index}", "moduleId": module_ids[index], "title": f"关键信号 {index + 1}", "meaning": "需要用小样本确认", "impact": 8 - index, "confidence": .65, "evidenceRefs": ["input:confirmed"], "action": "进入验证"} for index in range(3)]
    actions = [{"priority": index + 1, "sourceModule": module_ids[index], "title": f"验证动作 {index + 1}", "why": "降低关键不确定性", "metric": "目标行动数", "passThreshold": "≥3", "failThreshold": "连续2天为0则停止"} for index in range(3)]
    return {
        "schemaVersion": "fused-diagnosis-report-v2", "modelVersion": "xinghu-decision-model-v2.0.0",
        "decisionCockpit": {"state": "CONDITIONAL", "label": "满足条件后验证", "reason": "关键成本和需求证据尚未闭环。", "confidence": .62, "missingInformationWarning": ["外部需求证据"], "topReasons": ["利润有空间", "需求待证", "合规待核"], "mostInfluentialVariable": {"label": "海外零售价", "currentValue": 9.99, "threshold": "12.50 美元", "direction": "提高价格或降本", "explanation": "改变单位经济"}},
        "decisionModules": modules, "opportunities": cards, "blockingRisks": cards, "actions": actions,
        "unitEconomics": {"baseline": {"profitCny": 12, "marginRate": .18}, "completeness": "incomplete", "missingCosts": ["advertisingAllowanceCny"], "disclaimer": "不代表完整利润"},
    }


def restore_local_v5_context(snapshot: Dict) -> bool:
    profile = snapshot.get("productProfile", {}) if isinstance(snapshot, dict) else {}
    required = ["name", "category", "factoryPriceCny", "retailPriceUsd", "exchangeRate", "platformCommissionRate", "estimatedLogisticsCny", "weightG", "lengthCm", "widthCm", "heightCm", "customerType", "businessGoal"]
    if not isinstance(profile, dict) or any(key not in profile for key in required):
        return False
    product = ProductInput(
        name=str(profile["name"]), category=str(profile["category"]), factory_price_cny=float(profile["factoryPriceCny"]),
        retail_price_usd=float(profile["retailPriceUsd"]), exchange_rate=float(profile["exchangeRate"]),
        platform_commission_rate=float(profile["platformCommissionRate"]), estimated_logistics_cny=float(profile["estimatedLogisticsCny"]),
        weight_g=float(profile["weightG"]), length_cm=float(profile["lengthCm"]), width_cm=float(profile["widthCm"]), height_cm=float(profile["heightCm"]),
        material=str(profile.get("material") or "未填写"), has_battery=bool(profile.get("hasBattery")), has_magnet=bool(profile.get("hasMagnet")),
        is_liquid_or_powder=bool(profile.get("isLiquidOrPowder")), is_fragile=bool(profile.get("isFragile")),
        certifications=list(profile.get("certifications") or ["无"]), customer_type=str(profile["customerType"]),
        business_goal=str(profile["businessGoal"]), product_description=str(profile.get("description") or ""),
    )
    st.session_state["product"] = product
    st.session_state["report"] = evaluate_product(product)
    st.session_state["canonical_product"] = profile
    return True


def normalize_decision_report(report: Dict) -> Dict:
    schema = report.get("schemaVersion", "fused-diagnosis-report-v1") if isinstance(report, dict) else "fused-diagnosis-report-v1"
    if schema == "fused-diagnosis-report-v2":
        normalized = dict(report)
        normalized["sourceSchemaVersion"] = schema
        normalized["opportunities"] = list(report.get("opportunities", []))[:3]
        normalized["blockingRisks"] = list(report.get("blockingRisks", []))[:3]
        normalized["actions"] = list(report.get("actions", []))[:3]
        normalized["decisionModules"] = list(report.get("decisionModules", []))
        return normalized
    summary = report.get("executionSummary", {}) if isinstance(report, dict) else {}
    score = float(summary.get("totalScore", 0) or 0)
    state = "PROCEED" if score >= 72 else "CONDITIONAL" if score >= 48 else "PAUSE"
    labels = {"PROCEED": "建议进入验证", "CONDITIONAL": "满足条件后验证", "PAUSE": "暂缓投入"}
    missing = list(report.get("missingEvidence", [])) if isinstance(report, dict) else []
    placeholders = [
        {"title": "沿用 v5 确定性结论", "meaning": str(summary.get("conclusion", "已保存历史判断")), "confidence": .5, "action": "按原报告执行小样本验证"},
        {"title": "历史财务口径可追溯", "meaning": "价格、佣金与物流仍按原始快照展示", "confidence": .8, "action": "补齐广告与售后成本"},
        {"title": "报告无需重新分析", "meaning": "当前内容来自不可变历史快照", "confidence": 1, "action": "需要时创建新诊断"},
    ]
    risks = [{"title": item, "meaning": "历史报告未补写该证据", "confidence": 1, "action": "补证后重新验证"} for item in (missing + ["完整单位经济", "十二模块深度"])[0:3]]
    actions = [{"priority": i + 1, "title": card["action"], "why": card["meaning"], "metric": "证据闭环", "passThreshold": "取得可核验事实", "failThreshold": "仍未知则不扩大投入"} for i, card in enumerate(risks)]
    return {
        "sourceSchemaVersion": schema,
        "decisionCockpit": {"state": state, "label": labels[state], "reason": "这是历史报告兼容视图；原始快照未改写，建议结合 v2 新诊断补齐决策深度。", "confidence": float(report.get("confidence", {}).get("overall", .5) or .5), "missingInformationWarning": missing, "topReasons": [item["meaning"] for item in placeholders], "mostInfluentialVariable": {"label": "完整成本", "currentValue": "历史口径", "threshold": "补齐广告与售后成本", "direction": "先补证", "explanation": "历史报告未包含 v2 敏感性字段。"}},
        "opportunities": placeholders, "blockingRisks": risks, "actions": actions, "decisionModules": [],
        "unitEconomics": {"completeness": "incomplete", "baseline": {}, "missingCosts": ["v2 fields"], "disclaimer": "历史口径不代表完整利润"},
    }


def build_scenario_payload(name: str, baseline: Dict, *, retail_price_usd: float, logistics_cny: float, commission_rate: float, ad_allowance_cny: float, return_reserve_cny: float, market: str = "", channel: str = "") -> Dict:
    del baseline
    payload = {
        "schemaVersion": "diagnosis-scenario-v1", "name": name.strip() or "对比方案",
        "retailPriceUsd": float(retail_price_usd), "estimatedLogisticsCny": float(logistics_cny),
        "platformCommissionRate": float(commission_rate), "advertisingAllowanceCny": float(ad_allowance_cny),
        "returnAfterSalesReserveCny": float(return_reserve_cny), "persist": True,
    }
    if market.strip():
        payload["marketAssumption"] = market.strip()
    if channel.strip():
        payload["channelAssumption"] = channel.strip()
    return payload


def render_signal_cards(title: str, cards: List[Dict], kind: str):
    st.markdown(f"### {title}")
    columns = st.columns(3)
    for index, card in enumerate(cards[:3]):
        with columns[index]:
            st.markdown(
                f'<div class="signal-card {kind}"><div class="signal-rank">0{index + 1}</div><div class="signal-title">{html.escape(str(card.get("title", "待验证")))}</div><div class="signal-meaning">{html.escape(str(card.get("meaning", "")))}</div><div class="claim-meta">置信度 {float(card.get("confidence", 0)) * 100:.0f}% · 下一步：{html.escape(str(card.get("action", "补齐证据")))}</div></div>',
                unsafe_allow_html=True,
            )


def render_decision_cockpit(report: Dict):
    normalized = normalize_decision_report(report)
    cockpit = normalized["decisionCockpit"]
    style = {"PROCEED": "proceed", "CONDITIONAL": "conditional", "PAUSE": "pause"}.get(cockpit.get("state"), "conditional")
    missing = cockpit.get("missingInformationWarning", [])
    warning = " · 仍缺：" + "、".join(str(item) for item in missing[:3]) if missing else " · 关键输入已覆盖"
    st.markdown(
        f'<div class="cockpit {style}"><div class="decision-eyebrow">DECISION COCKPIT · 先看结论</div><div class="decision-label">{html.escape(str(cockpit.get("label", "满足条件后验证")))}</div><div class="decision-reason">{html.escape(str(cockpit.get("reason", "")))}</div><div class="confidence-line">决策置信度 {float(cockpit.get("confidence", 0)) * 100:.0f}%{html.escape(warning)}</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("#### 三个最强判断依据")
    for reason in cockpit.get("topReasons", [])[:3]:
        st.markdown(f"- {reason}")
    render_signal_cards("前三个机会", normalized.get("opportunities", []), "opportunity")
    render_signal_cards("三个阻断风险", normalized.get("blockingRisks", []), "blocking")
    variable = cockpit.get("mostInfluentialVariable", {})
    st.markdown("### 最可能改变结论的变量")
    st.markdown(f'<div class="section-card"><div class="journey-kicker">MOST INFLUENTIAL</div><div class="journey-title">{html.escape(str(variable.get("label", "关键成本")))}</div><p><b>当前：</b>{html.escape(str(variable.get("currentValue", "未知")))}　<b>改变门槛：</b>{html.escape(str(variable.get("threshold", "待补证")))}</p><p>{html.escape(str(variable.get("explanation", "")))} · {html.escape(str(variable.get("direction", "先补证")))}</p></div>', unsafe_allow_html=True)
    st.markdown("### 接下来只做三件事")
    for action in normalized.get("actions", [])[:3]:
        st.markdown(f'<div class="action-card"><b>{int(action.get("priority", 1))}. {html.escape(str(action.get("title", "验证")))}</b><div>{html.escape(str(action.get("why", "")))}</div><div class="threshold">通过：{html.escape(str(action.get("passThreshold", "达到验证门槛")))} ｜ 停止：{html.escape(str(action.get("failThreshold", "越过止损线")))}</div></div>', unsafe_allow_html=True)
    st.markdown("<small>可执行动作：返回上方修正输入、在下方比较场景，或展开模块检查证据。多源融合增量报告已保存；共识保留，冲突可见，未知不补写。</small>", unsafe_allow_html=True)
    return normalized


def render_module_exploration(normalized: Dict):
    modules = normalized.get("decisionModules", [])
    st.markdown("## 二、按需深入：十二个决策模块")
    if not modules:
        st.info("这是 v1 历史快照。十二模块没有被伪造或回填；请创建一次新诊断以获得 v2 深度结果。")
        return
    for index, module in enumerate(modules, start=1):
        with st.expander(f"{index:02d} · {module.get('label', '决策模块')}｜{module.get('score', 0)}分 · 权重{module.get('weight', 0)}% · 置信度{float(module.get('confidence', 0)) * 100:.0f}%"):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**事实 / 证据引用**")
                for item in module.get("evidenceRefs", []) or ["无外部证据"]:
                    st.write(f"- {item}")
                st.markdown("**正向驱动**")
                for item in module.get("positiveDrivers", []): st.write(f"- {item}")
                st.markdown("**推断（待验证）**")
                for item in module.get("inferences", []): st.write(f"- {item}")
            with c2:
                st.markdown("**未知 / 缺失**")
                for item in module.get("unknowns", []) or ["未发现显式缺失"]: st.write(f"- {item}")
                st.markdown("**失分原因**")
                for item in module.get("lostScoreDrivers", []): st.write(f"- {item}")
                st.markdown("**改善杠杆**")
                for item in module.get("improvementLevers", []): st.write(f"- {item}")
            st.info(f"下一验证问题：{module.get('nextValidationQuestion', '')}\n\n通过门槛：{module.get('validationThreshold', '')}")
            st.caption(" → ".join(str(item) for item in module.get("causalChain", [])))


def render_scenario_lab(client: DiagnosisApiClient, normalized: Dict, raw_report: Dict):
    st.markdown("## 三、场景实验室")
    profile = raw_report.get("productProfile", {})
    if not profile or normalized.get("sourceSchemaVersion") != "fused-diagnosis-report-v2":
        st.info("v2 基线完成后可比较售价、物流、佣金、广告、售后准备金与市场/渠道假设。")
        return
    economics = normalized.get("unitEconomics", {}).get("baseline", {})
    with st.form("scenario_lab_form"):
        st.caption("场景只创建新的不可变对比版本，不修改用户确认的基线。")
        name = st.text_input("场景名称", value="可行性改善方案")
        a, b, c = st.columns(3)
        with a:
            price = st.number_input("场景售价（美元）", min_value=0.0, value=float(profile.get("retailPriceUsd", 0.0)))
            logistics = st.number_input("场景物流费（人民币）", min_value=0.0, value=float(profile.get("estimatedLogisticsCny", 0.0)))
        with b:
            commission = st.number_input("场景平台佣金率", min_value=0.0, max_value=0.5, value=float(profile.get("platformCommissionRate", 0.0)), step=.01)
            ad = st.number_input("广告成本 allowance（人民币）", min_value=0.0, value=float(economics.get("advertisingAllowanceCny", 0.0)))
        with c:
            returns = st.number_input("退货售后准备金（人民币）", min_value=0.0, value=float(economics.get("returnAfterSalesReserveCny", 0.0)))
            market = st.text_input("场景市场假设", value=(profile.get("intendedMarkets") or [""])[0])
            channel = st.text_input("场景渠道假设", value=(profile.get("intendedChannels") or [""])[0])
        submitted = st.form_submit_button("计算并保存场景对比", width="stretch")
    if submitted:
        try:
            handle = st.session_state["diagnosis_handle"]
            payload = build_scenario_payload(name, profile, retail_price_usd=price, logistics_cny=logistics, commission_rate=commission, ad_allowance_cny=ad, return_reserve_cny=returns, market=market, channel=channel)
            st.session_state["scenario_result"] = client.scenario(handle["diagnosisId"], handle["accessToken"], payload)
            st.success("场景已作为新版本保存；基线未改变。")
        except (DiagnosisApiError, KeyError) as exc:
            st.error(str(exc) if str(exc) else "场景暂时无法保存。")
    saved = st.session_state.get("scenario_result", {}).get("result")
    if saved:
        base, alt, delta = saved.get("baseline", {}), saved.get("alternative", {}), saved.get("deltas", {})
        x, y = st.columns(2)
        with x: render_metric("基线利润", f"{base.get('profitCny', 0)} 元", base.get("decisionLabel", ""))
        with y: render_metric("方案利润", f"{alt.get('profitCny', 0)} 元", alt.get("decisionLabel", ""))
        direction = "delta-up" if float(delta.get("profitCny", 0)) >= 0 else "delta-down"
        st.markdown(f'<p class="{direction}">利润变化 {float(delta.get("profitCny", 0)):+.2f} 元 · 综合分 {float(delta.get("weightedScore", 0)):+.1f} · 风险 {float(delta.get("riskScore", 0)):+.1f}</p>', unsafe_allow_html=True)
        for module in saved.get("affectedModules", []):
            st.write(f"- {module.get('id')} {float(module.get('scoreDelta', 0)):+.1f}：{'；'.join(module.get('reasons', []))}")


def render_professional_report(product: ProductInput, report: Dict, client: DiagnosisApiClient):
    decision = report["decision"]
    st.markdown("## 四、专业版 v5 完整报告")
    st.table([{"项目": key, "内容": value} for key, value in decision.items()])
    st.markdown("### 七维评分矩阵")
    score_rows = []
    for dimension, score in report["scores"].items():
        score_rows.append({"评估维度": dimension, "得分": score, "满分": MAX_SCORES[dimension], "风险等级": risk_level(score, MAX_SCORES[dimension])})
        st.write(f"**{dimension}：{score} / {MAX_SCORES[dimension]}**")
        st.progress(score / MAX_SCORES[dimension])
    st.table(score_rows)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["产品画像", "经营测算", "平台匹配", "风险说明", "OPC任务与验证路径"])
    with tab1:
        st.table([{"特征项": key, "识别结果": str(value)} for key, value in report["vector"].items()])
    with tab2:
        keys = ["海外零售价人民币口径", "出厂价", "估算平台佣金", "估算单件物流费", "估算单件利润", "扣费后利润率", "单件最大可承受广告成本"]
        st.table([{"项目": key, "数值": report["vector"].get(key)} for key in keys])
    with tab3:
        for platform, data in report["platform_match"].items():
            st.markdown(f"**{platform}｜匹配分 {data['匹配分']} / 100**")
            st.write("；".join(data["匹配理由"]))
    with tab4:
        for title, notes in report["notes"].items():
            st.markdown(f"**{title}**")
            for note in notes: st.write(f"- {note}")
    with tab5:
        st.table([{"序号": i, **task} for i, task in enumerate(report["tasks"], start=1)])
        st.markdown("#### 7天小样本验证路径")
        st.table([
            {"阶段": "准备期", "时间": "D1-D2", "核心动作": "补齐认证、物流、竞品、素材和Listing草稿", "输出结果": "测试准备包"},
            {"阶段": "上架期", "时间": "D3", "核心动作": "完成平台测试页面或询盘页搭建", "输出结果": "初始测试链接"},
            {"阶段": "测试期", "时间": "D4-D6", "核心动作": "记录曝光、点击、加购、询盘与成本", "输出结果": "测试数据表"},
            {"阶段": "复盘期", "时间": "D7", "核心动作": "按通过/停止阈值复盘", "输出结果": "继续或停止决定"},
        ])
    render_fused_report(client)


def main():
    st.set_page_config(page_title="星狐AI跨境商品诊断舱", page_icon="🦊", layout="wide")
    st.markdown('<meta name="google" content="notranslate">', unsafe_allow_html=True)
    load_css()
    diagnosis_client = get_diagnosis_client()
    render_diagnosis_reloader(diagnosis_client)
    st.markdown('<div class="hero notranslate"><div class="pill">决策优先 · 证据约束 · Demo v5 兼容</div><h1>星狐AI跨境商品诊断舱</h1><p>先回答该不该验证、为什么、什么会改变结论；再按需展开全部专业细节。</p></div>', unsafe_allow_html=True)

    with st.expander("快速载入演示案例", expanded=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            sample_choice = st.selectbox("选择一个演示样本", ["不使用样本，手动填写"] + list(SAMPLE_CASES.keys()), help="保留 v5 三类权威样本。")
        with c2:
            st.write(""); st.write("")
            if st.button("载入所选样本", width="stretch"):
                if sample_choice != "不使用样本，手动填写":
                    apply_sample(sample_choice); st.success("样本已载入，所有字段仍可修正。"); st.rerun()

    render_image_workspace(diagnosis_client)
    required_keys = ["name", "category", "factory_price_cny", "retail_price_usd", "estimated_logistics_cny", "customer_type", "business_goal"]
    completed = sum(bool(st.session_state.get(key)) and st.session_state.get(key) != "请选择" for key in required_keys)
    st.markdown('<div class="journey-kicker">GUIDED INPUT · 六步确认</div><div class="journey-title">把复杂输入变成一条清晰路径</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="completion-shell">关键输入完成 {completed}/{len(required_keys)}。价格、物流、广告/售后成本与需求证据会直接影响置信度和决策。</div>', unsafe_allow_html=True)
    st.progress(completed / len(required_keys))

    with st.form("demo_form"):
        with st.expander("01 · 产品基础", expanded=True):
            a, b = st.columns(2)
            with a:
                name = st.text_input("产品名称 *", placeholder="例如：硬质合金铣刀", key="name")
                category = st.text_input("产品类目 *", placeholder="例如：工业刀具", key="category")
            with b:
                material = st.text_input("产品材质", placeholder="例如：钨钢", key="material")
                aliases = st.text_input("产品别名", placeholder="多个别名用逗号分隔", key="canonical_aliases")
            product_description = st.text_area("产品描述 / 使用场景 / 核心卖点", placeholder="用途、目标客户、场景与差异点", key="product_description", height=116)
            specifications = st.text_area("规格参数", placeholder="例如：直径6mm, 四刃", key="canonical_specifications", height=70)
            use_scenarios = st.text_input("使用场景", placeholder="例如：CNC加工", key="canonical_use_scenarios")
        with st.expander("02 · 客户与业务目标"):
            a, b = st.columns(2)
            with a:
                customer_type = st.selectbox("目标客户类型 *", ["请选择", "C端消费者", "小B商家", "工厂客户"], key="customer_type")
                purchaser_roles = st.text_input("采购角色", placeholder="工厂采购, 经销商", key="canonical_purchaser_roles")
            with b:
                business_goal = st.selectbox("企业诉求 *", ["请选择", "测品", "找订单", "做品牌", "清库存", "建渠道"], key="business_goal")
                user_roles = st.text_input("实际使用者", placeholder="机加工操作员", key="canonical_user_roles")
        with st.expander("03 · 价格、成本与物流"):
            a, b, c = st.columns(3)
            with a:
                factory_price_cny = st.text_input("出厂价（人民币）*", placeholder="45", key="factory_price_cny")
                retail_price_usd = st.text_input("建议海外零售价（美元）*", placeholder="29.99", key="retail_price_usd")
                exchange_rate = st.text_input("汇率（美元兑人民币）*", placeholder="7.2", key="exchange_rate")
            with b:
                platform_commission_rate = st.text_input("平台佣金率 *", placeholder="0.15", key="platform_commission_rate")
                estimated_logistics_cny = st.text_input("估算单件物流费（人民币）*", placeholder="18", key="estimated_logistics_cny")
                advertising_allowance = st.text_input("广告成本 allowance（人民币，可选）", key="advertising_allowance")
                return_reserve = st.text_input("退货售后准备金（人民币，可选）", key="return_reserve")
            with c:
                weight_g = st.text_input("产品重量（g）*", placeholder="850", key="weight_g")
                length_cm = st.text_input("包装长度（cm）*", placeholder="25", key="length_cm")
                width_cm = st.text_input("包装宽度（cm）*", placeholder="15", key="width_cm")
                height_cm = st.text_input("包装高度（cm）*", placeholder="12", key="height_cm")
        with st.expander("04 · 合规与特殊属性"):
            a, b, c, d = st.columns(4)
            with a: has_battery = st.checkbox("带电", key="has_battery")
            with b: has_magnet = st.checkbox("带磁", key="has_magnet")
            with c: is_liquid_or_powder = st.checkbox("液体/粉末", key="is_liquid_or_powder")
            with d: is_fragile = st.checkbox("易碎", key="is_fragile")
            certifications = st.multiselect("已有认证", ["无", "CE", "FCC", "RoHS", "FDA", "UKCA", "UL", "REACH"], key="certifications", placeholder="请选择已有认证")
        with st.expander("05 · 市场、渠道与缺失证据"):
            a, b = st.columns(2)
            with a:
                intended_markets = st.text_input("意向市场", placeholder="德国, 美国", key="canonical_intended_markets")
                intended_channels = st.text_input("意向渠道", placeholder="B2B平台, 独立站", key="canonical_intended_channels")
                market_demand_evidence = st.text_area("可核验的市场需求证据", placeholder="公开数据/询盘/成交证据引用；没有请留空", key="market_demand_evidence", height=70)
                competitor_evidence = st.text_area("竞品证据", placeholder="竞品样本、价格、差评或卖点引用", key="competitor_evidence", height=70)
            with b:
                missing_information = st.text_area("仍不确定 / 待补证据", placeholder="目标国认证要求, 实际运价", key="canonical_missing_information", height=70)
                moq_units = st.text_input("MOQ（可选）", key="moq_units")
                monthly_capacity = st.text_input("月产能（可选）", key="monthly_capacity")
                lead_time_days = st.text_input("交期天数（可选）", key="lead_time_days")
            c1, c2, c3 = st.columns(3)
            with c1: quality_control_ready = st.selectbox("质量控制是否就绪", ["未知", "是", "否"], key="quality_control_ready")
            with c2: localized_content_ready = st.selectbox("本地化素材是否就绪", ["未知", "是", "否"], key="localized_content_ready")
            with c3: operations_owner_ready = st.selectbox("运营负责人是否就绪", ["未知", "是", "否"], key="operations_owner_ready")
            validation_budget = st.text_input("7天验证预算（人民币，可选）", key="validation_budget")
            validation_window_days = st.text_input("验证窗口天数（可选）", key="validation_window_days")
        with st.expander("06 · 复核并确认"):
            st.info("提交即确认：手动修正优先于图片建议；未知项保持未知；基线报告保存后不会被场景静默覆盖。")
        submitted = st.form_submit_button("生成诊断报告", width="stretch", help="确认输入并生成决策优先报告")

    if submitted:
        errors = []
        if not name.strip(): errors.append("产品名称不能为空。")
        if not category.strip(): errors.append("产品类目不能为空。")
        if customer_type == "请选择": errors.append("请选择目标客户类型。")
        if business_goal == "请选择": errors.append("请选择企业诉求。")
        factory_price = parse_float("出厂价", factory_price_cny, errors)
        retail_price = parse_float("建议海外零售价", retail_price_usd, errors)
        rate = parse_float("汇率", exchange_rate, errors, min_value=.1)
        commission = parse_float("平台佣金率", platform_commission_rate, errors)
        logistics = parse_float("估算单件物流费", estimated_logistics_cny, errors)
        weight = parse_float("产品重量", weight_g, errors)
        length = parse_float("包装长度", length_cm, errors)
        width = parse_float("包装宽度", width_cm, errors)
        height = parse_float("包装高度", height_cm, errors)
        if commission > .5: errors.append("平台佣金率建议填写0到0.5之间，例如0.15。")
        if errors:
            st.error("请先修正以下信息："); [st.write(f"- {error}") for error in errors]; return
        product = ProductInput(name.strip(), category.strip(), factory_price, retail_price, rate, commission, logistics, weight, length, width, height, material.strip() or "未填写", has_battery, has_magnet, is_liquid_or_powder, is_fragile, certifications or ["无"], customer_type, business_goal, product_description.strip())
        report = evaluate_product(product)
        st.session_state["report"], st.session_state["product"] = report, product
        extras = {
            "aliases": aliases, "specifications": specifications, "use_scenarios": use_scenarios, "purchaser_roles": purchaser_roles,
            "user_roles": user_roles, "intended_markets": intended_markets, "intended_channels": intended_channels,
            "missing_information": missing_information, "advertising_allowance": advertising_allowance, "return_reserve": return_reserve,
            "market_demand_evidence": market_demand_evidence, "competitor_evidence": competitor_evidence, "moq_units": moq_units,
            "monthly_capacity": monthly_capacity, "lead_time_days": lead_time_days, "quality_control_ready": quality_control_ready,
            "localized_content_ready": localized_content_ready, "operations_owner_ready": operations_owner_ready,
            "validation_budget": validation_budget, "validation_window_days": validation_window_days,
        }
        canonical = build_canonical_product(product, extras, report)
        st.session_state["canonical_product"] = canonical
        start_remote_diagnosis(diagnosis_client, canonical)

    refresh_remote_diagnosis(diagnosis_client)
    if "report" in st.session_state and "product" in st.session_state:
        report, product = st.session_state["report"], st.session_state["product"]
        fused = st.session_state.get("fused_result", {}).get("report")
        if not fused:
            fused = {"schemaVersion": "fused-diagnosis-report-v1", "executionSummary": {"totalScore": report["total_score"], "conclusion": report["decision"]["综合结论"]}, "confidence": {"overall": .5}, "missingEvidence": ["v2 深度报告仍在生成"]}
        st.markdown("---")
        st.markdown(f'<div class="report-title"><h2>产品适配度诊断报告</h2><p>诊断对象：{html.escape(product.name)} ｜ v5 兼容 + 决策模型 v2</p></div>', unsafe_allow_html=True)
        normalized = render_decision_cockpit(fused)
        md = generate_markdown_report(product, report)
        st.markdown("<small>专业版 v5 完整报告（执行摘要、经营测算、七维评分、平台、风险、OPC 与7天路径）默认收起，原有内容完整保留。</small>", unsafe_allow_html=True)
        st.download_button("下载完整诊断报告", md, file_name=f"{product.name}_跨境电商适配度诊断报告.md", mime="text/markdown", width="stretch")
        render_module_exploration(normalized)
        render_scenario_lab(diagnosis_client, normalized, fused)
        show_professional = st.toggle("展开专业版 v5 完整报告、证据与反馈", value=False)
        if show_professional:
            render_professional_report(product, report, diagnosis_client)


if __name__ == "__main__":
    main()
