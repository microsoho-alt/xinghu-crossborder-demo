# 星狐AI跨境商品诊断舱 Demo v4

这是外部演示版，特点：

1. 默认空白输入，不预设产品数据。
2. 增加商业化UI设计。
3. 保留“填入测试样例”按钮，放在折叠区，不影响正式演示。
4. 不保存用户输入，不连接数据库，不调用外部接口。
5. 适合部署到 Streamlit Community Cloud 做公开Demo。

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 建议演示产品

1. C端消费品：车载手机支架
2. B端工业品：硬质合金铣刀
3. 带电小家电：便携式迷你吸尘器

## 文件结构

```text
app.py
requirements.txt
README.md
.streamlit/config.toml
```