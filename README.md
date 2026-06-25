# 星狐AI跨境商品诊断舱 Demo v5

这是外部演示增强版。

## v5升级内容

1. 增加三个演示案例下拉框：
   - 案例1：C端红海消费品｜车载手机支架
   - 案例2：B端工业品｜硬质合金铣刀
   - 案例3：带电小家电｜便携式迷你吸尘器

2. 诊断报告升级为可交付版：
   - 执行摘要
   - 产品基础画像
   - 经营测算模型
   - 七维评分矩阵
   - 平台适配与渠道建议
   - 风险提示与补强方向
   - OPC运营任务拆解
   - 7天小样本验证路径
   - 数据回流字段
   - 技术链路说明

3. 默认仍然支持手动填写真实产品数据。

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 公网部署

上传以下文件到 GitHub 仓库：

```text
app.py
requirements.txt
README.md
.streamlit/config.toml
```

Streamlit Community Cloud 入口文件选择：

```text
app.py
```
