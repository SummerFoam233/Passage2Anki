from aqt import mw
from anki.notes import Note
from anki.stdmodels import addBasicModel

def add_or_get_model(model_name="Passage2Card", fields=("Front", "Back"), templates=None):
    col = mw.col  # 获取当前的集合
    model = col.models.byName(model_name)
    if not model:  # 如果模型不存在，创建一个新的
        model = col.models.new(model_name)  # 创建一个新模型
        
        # 添加字段
        for field_name in fields:
            field = col.models.newField(field_name)
            col.models.addField(model, field)
        
        # 设置正面和背面模板
        if templates:
            tmpl = col.models.newTemplate("Card 1")
            tmpl['qfmt'] = templates[0]  # 正面模板
            tmpl['afmt'] = templates[1]  # 背面模板
            col.models.addTemplate(model, tmpl)
        
        col.models.add(model)  # 将新模型添加到集合中
    else:
        # 如果模型已存在，可以选择更新模板或字段等
        pass
    
    return model

def add_cards_to_deck(deck_name, data_list):
    col = mw.col  # 获取当前的集合
    deck_id = col.decks.id(deck_name)
    col.decks.select(deck_id)

    model_name = "Passage2Card"
    front_template = "{{Front}}"
    back_template = "{{FrontSide}}<hr id=answer style=\"border: 1px solid #9A9A9A;\">{{Back}}"
    templates = (front_template, back_template)

    model = add_or_get_model(model_name=model_name, templates=templates)

    col.models.setCurrent(model)
    model['did'] = deck_id
    col.models.save(model)

    for front, back in data_list:
        note = col.newNote()
        note.model()['did'] = deck_id  # 确保笔记添加到正确的牌组
        note["Front"] = front
        note["Back"] = back
        col.addNote(note)

    col.save()
