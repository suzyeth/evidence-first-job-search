# Markdown → PDF

## 一次性准备

- Pandoc:`winget install --id JohnMacFarlane.Pandoc`(macOS:`brew install pandoc`)
- wkhtmltopdf:`winget install --id wkhtmltopdf.wkhtmltox`(macOS:`brew install --cask wkhtmltopdf`)
- 含中文的文档:`pip install weasyprint`(wkhtmltopdf 不带 CJK 字体)

## 简历

在 track 目录下运行:

```bash
pandoc resume.md -o resume.pdf --css ../pdf-template/resume.css --pdf-engine=wkhtmltopdf --pdf-engine-opt=--enable-local-file-access
```

中文:把 `--pdf-engine` 换成 `weasyprint`(并去掉 `--pdf-engine-opt`)。

## 求职信

用**独立样式表** `cover-letter.css`(用 resume.css 会把名字渲染成简历大标题)。工作稿里通常有大量批注,渲染前另存一个只含正文的干净版,结构见 `templates/cover-letter-skeleton.md`。

```bash
pandoc _cover_letter_clean.md -o First_Last_CoverLetter_Company.pdf --css ../../pdf-template/cover-letter.css -f markdown+raw_html --pdf-engine=wkhtmltopdf --pdf-engine-opt=--enable-local-file-access
```

- 必须加 `-f markdown+raw_html`,否则内嵌 `<div>` 会被吞掉
- raw HTML 块里的链接必须写 `<a href>`,markdown 链接不会被解析
- 转完删掉临时干净版

## 命名

```
First_Last_Resume_<Track>.pdf
First_Last_Resume_<Track>_<Company>.pdf
First_Last_CoverLetter_<Company>.pdf
```

下划线分隔,无空格(老 ATS 对空格不友好)。

## 检查

- [ ] 字体统一、无裁切
- [ ] 链接可点
- [ ] 简历 ≤ 2 页,求职信 1 页
- [ ] < 1 MB
- [ ] PDF 文字可选中复制(ATS 能读)
- [ ] 不要用在线 PDF 转换器(数据会上传第三方)
