from tools.word_builder import WordBuilder

word = WordBuilder()
word.add_heading("0级标题", level=0)
word.add_heading("1级标题", level=1)

word.add_paragraph("普通段落1")
word.add_paragraph("普通段落2")

word.save("test.docx")