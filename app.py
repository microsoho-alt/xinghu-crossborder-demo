import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

import streamlit as st


# =========================================================
# 星狐 AI 跨境商品诊断舱 v4
# 外部演示版：默认空白输入 + 简洁商业化UI + 公开部署友好
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
            font-family: "Microsoft YaHei", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
        }
        .block-container {
            padding-top: 1.4rem;
            max-width: 1180px;
        }
        .hero {
            padding: 28px 32px;
            border-radius: 24px;
            background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 48%, #2563eb 100%);
            color: #fff;
            margin-bottom: 22px;
            box-shadow: 0 16px 40px rgba(15, 23, 42, 0.18);
        }
        .hero h1 {
            font-size: 34px;
            line-height: 1.15;
            margin: 0 0 8px 0;
            letter-spacing: -0.5px;
        }
        .hero p {
            margin: 0;
            color: rgba(255, 255, 255, .82);
            font-size: 15px;
        }
        .pill {
            display: inline-block;
            margin-bottom: 14px;
            padding: 6px 12px;
            border-radius: 999px;
            background: rgba(255, 255, 255, .14);
            color: rgba(255, 255, 255, .92);
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
            min-height: 110px;
        }
        .metric-label {
            font-size: 13px;
            color: #64748b;
            margin-bottom: 8px;
        }
        .metric-value {
            font-size: 30px;
            font-weight: 800;
            color: #0f172a;
            line-height: 1.1;
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
        .muted {
            color: #64748b;
            font-size: 13px;
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
        div[data-testid="stForm"] {
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 20px;
            background: #ffffff;
            box-shadow: 0 8px 28px rgba(15, 23, 42, 0.04);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def clamp(value: float, min_value: int, max_value: int) -> int:
    return int(max(min_value, min(max_value, round(value))))


def contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword.lower() in text.lower() for keyword in keywords)


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
        "估算单件利润": estimated_single_profit_cny(product),
        "扣费后利润率": margin,
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
        tasks.append({"触发原因": "合规风险偏高", "任务": "核查目标市场认证、平台禁限售、运输申报要求，形成合规资料清单。"})
    if scores["物流履约适配度"] <= 10:
        tasks.append({"触发原因": "物流履约压力", "任务": "向至少3家物流服务商询价，确认可发渠道、计费重量、异常件处理和退货规则。"})
    if scores["利润空间适配度"] <= 12:
        tasks.append({"触发原因": "利润空间偏紧", "任务": "重算价格模型，拆分出厂价、平台佣金、物流费、广告费和售后成本。"})
    if scores["内容传播适配度"] <= 6:
        tasks.append({"触发原因": "内容素材不足", "任务": "补拍产品使用场景素材，提炼用户痛点、差异化卖点和短视频脚本。"})
    if scores["竞争强度修正值"] <= 2:
        tasks.append({"触发原因": "红海竞争", "任务": "完成差异化竞品分析，围绕场景、人群、套装、包装、价格带设计破局方案。"})

    platforms = recommend_platforms(platform_match)
    tasks.extend([
        {"触发原因": "平台测试准备", "任务": f"围绕推荐平台（{'、'.join(platforms)}）完成20个海外竞品样本分析。"},
        {"触发原因": "Listing冷启动", "任务": "生成英文标题、五点描述、长描述、搜索关键词和FAQ草稿。"},
        {"触发原因": "素材标准化", "任务": "整理主图、场景图、尺寸图、卖点图、包装图和工厂资质素材。"},
        {"触发原因": "小预算验证", "任务": "设计7天测品计划，设定曝光、点击、转化、询盘、加购和退款指标。"},
        {"触发原因": "数据回流", "任务": "建立数据复盘表，把测试结果回流到产品适配度评分模型。"},
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

    return {
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
        "tasks": generate_opc_tasks(product, scores, platform_match),
    }


def generate_markdown_report(product: ProductInput, report: Dict) -> str:
    lines = []
    lines.append(f"# {product.name} 跨境电商适配度诊断报告\n")
    lines.append("## 一、诊断结论")
    lines.append(f"- 总分：{report['total_score']} / 100")
    lines.append(f"- 等级：{report['level']}")
    lines.append(f"- 推荐平台：{'、'.join(report['platforms'])}")
    lines.append(f"- 推荐市场：{'、'.join(report['markets'])}\n")

    lines.append("## 二、产品特征")
    for k, v in report["vector"].items():
        lines.append(f"- {k}：{v}")
    lines.append("")

    lines.append("## 三、维度评分")
    for k, v in report["scores"].items():
        lines.append(f"- {k}：{v}/{MAX_SCORES[k]}")
    lines.append("")

    lines.append("## 四、平台匹配")
    for platform, data in report["platform_match"].items():
        lines.append(f"### {platform}")
        lines.append(f"- 匹配分：{data['匹配分']}/100")
        for reason in data["匹配理由"]:
            lines.append(f"- {reason}")
    lines.append("")

    lines.append("## 五、OPC运营任务")
    for i, task in enumerate(report["tasks"], start=1):
        lines.append(f"{i}. 【{task['触发原因']}】{task['任务']}")

    lines.append("\n## 六、技术链路")
    lines.append("产品数据采集 → 标准化处理 → 产品特征向量生成 → 平台规则匹配 → 多维权重评分 → 风险提示 → OPC任务生成 → 数据回流")
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


def fill_sample():
    st.session_state["name"] = "车载手机支架"
    st.session_state["category"] = "汽配 手机支架"
    st.session_state["factory_price_cny"] = "18"
    st.session_state["retail_price_usd"] = "9.99"
    st.session_state["exchange_rate"] = "7.2"
    st.session_state["platform_commission_rate"] = "0.15"
    st.session_state["estimated_logistics_cny"] = "18"
    st.session_state["weight_g"] = "200"
    st.session_state["length_cm"] = "10"
    st.session_state["width_cm"] = "8"
    st.session_state["height_cm"] = "5"
    st.session_state["material"] = "ABS塑料"
    st.session_state["customer_type"] = "C端消费者"
    st.session_state["business_goal"] = "测品"
    st.session_state["certifications"] = ["无"]
    st.session_state["product_description"] = "用于汽车出风口或中控台固定手机，适合导航、充电、长途驾驶场景，安装方便。"


def main():
    st.set_page_config(page_title="星狐AI跨境商品诊断舱 Demo", page_icon="🦊", layout="wide")
    st.markdown('<meta name="google" content="notranslate">', unsafe_allow_html=True)
    load_css()

    st.markdown(
        """
        <div class="hero notranslate">
            <div class="pill">AI + 跨境电商 · 产品出海前置诊断 Demo</div>
            <h1>星狐AI跨境商品诊断舱</h1>
            <p>输入一个制造业产品，系统自动完成特征识别、平台匹配、利润测算、风险提示与OPC任务生成。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("演示说明", expanded=False):
        st.write("本Demo默认不预填任何产品数据。演示人可现场输入真实产品信息，点击生成诊断报告。")
        st.write("当前版本不保存用户输入，不连接数据库，不调用外部接口。刷新页面后数据不会持久保留。")
        if st.button("填入一个测试样例"):
            fill_sample()
            st.rerun()

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
                has_battery = st.checkbox("带电")
            with b:
                has_magnet = st.checkbox("带磁")
            with c:
                is_liquid_or_powder = st.checkbox("液体/粉末")
            with d:
                is_fragile = st.checkbox("易碎")

            c3, c4 = st.columns(2)
            with c3:
                certifications = st.multiselect(
                    "已有认证",
                    ["无", "CE", "FCC", "RoHS", "FDA", "UKCA", "UL", "REACH"],
                    default=[],
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
                height=110
            )

            submitted = st.form_submit_button("生成诊断报告", use_container_width=True)

    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.markdown('<div class="small-title">Demo输出内容</div>', unsafe_allow_html=True)
        st.write("系统将自动输出：")
        render_tags(["跨境适配度评分", "推荐平台", "推荐市场"])
        render_tags(["利润测算", "物流风险", "合规风险"], "risk")
        render_tags(["产品特征向量", "平台规则匹配", "OPC任务清单"], "ok")
        st.markdown('<div class="footer-note">建议演示时准备3个产品：一个C端消费品、一个B端工业品、一个带电小家电，这样更容易体现系统判断差异。</div>', unsafe_allow_html=True)
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

    if "report" in st.session_state and "product" in st.session_state:
        report = st.session_state["report"]
        product = st.session_state["product"]

        st.markdown("---")
        st.markdown("## 二、诊断结果")

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            render_metric("跨境适配度总分", f"{report['total_score']}/100", "综合评分")
        with m2:
            render_metric("诊断等级", report["level"], "系统结论")
        with m3:
            render_metric("计费重量", f"{report['vector']['计费重量kg']} kg", report["vector"]["物流重量带"])
        with m4:
            render_metric("扣费后利润率", f"{report['vector']['扣费后利润率'] * 100:.1f}%", f"单件利润 {report['vector']['估算单件利润']} 元")

        colp, colm = st.columns(2)
        with colp:
            st.markdown("### 推荐平台")
            render_tags(report["platforms"])
        with colm:
            st.markdown("### 推荐市场")
            render_tags(report["markets"])

        st.markdown("### 七维评分")
        for dimension, score in report["scores"].items():
            st.write(f"**{dimension}：{score} / {MAX_SCORES[dimension]}**")
            st.progress(score / MAX_SCORES[dimension])

        tab1, tab2, tab3, tab4 = st.tabs(["产品特征", "平台匹配", "风险说明", "OPC任务"])

        with tab1:
            rows = [{"特征项": k, "识别结果": v} for k, v in report["vector"].items()]
            st.table(rows)

        with tab2:
            for platform, data in report["platform_match"].items():
                with st.expander(f"{platform}｜匹配分 {data['匹配分']} / 100", expanded=False):
                    st.write("**匹配理由**")
                    for reason in data["匹配理由"]:
                        st.write(f"- {reason}")
                    st.write("**适合项**")
                    render_tags(data["适合项"], "ok")
                    st.write("**限制项**")
                    render_tags(data["限制项"], "risk")

        with tab3:
            for title, notes in report["notes"].items():
                with st.expander(title, expanded=True):
                    for note in notes:
                        st.write(f"- {note}")

        with tab4:
            for i, task in enumerate(report["tasks"], start=1):
                st.write(f"{i}. **【{task['触发原因']}】** {task['任务']}")

        st.markdown("### 导出报告")
        md = generate_markdown_report(product, report)
        st.download_button(
            label="下载诊断报告",
            data=md,
            file_name=f"{product.name}_跨境电商适配度诊断报告.md",
            mime="text/markdown",
            use_container_width=True,
        )

        st.markdown(
            """
            <div class="footer-note">
            专利样机技术链路：产品数据采集 → 标准化处理 → 产品特征向量生成 → 平台规则匹配 → 多维权重评分 → 风险提示 → OPC任务生成 → 数据回流。
            </div>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()