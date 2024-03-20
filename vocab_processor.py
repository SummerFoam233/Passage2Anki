import re
import hashlib
import uuid
import time
import requests
import os
import json
import logging
logging.basicConfig(filename='/Users/summerfoam233/Desktop/备份/error.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
class TranslationError(Exception):
    """Exception raised when an error occurs in the translation process."""
    pass

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "Passage2Card.config")
    try:
        with open(config_path, 'r', encoding='utf-8') as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        return {}
    
def youdaoTranslate(translate_text,flag=1):
    '''
    :param translate_text: 待翻译的句子
    :param flag: 1:原句子翻译成英文；0:原句子翻译成中文
    :return: 返回翻译结果
    '''
    youdao_url = 'https://openapi.youdao.com/api'  # 有道api地址

    # 翻译文本生成sign前进行的处理
    input_text = ""
    config = load_config()
    # 当文本长度小于等于20时，取文本
    if (len(translate_text) <= 20):
        input_text = translate_text

    # 当文本长度大于20时，进行特殊处理
    elif (len(translate_text) > 20):
        input_text = translate_text[:10] + str(len(translate_text)) + translate_text[-10:]

    time_curtime = int(time.time())  # 秒级时间戳获取
    app_id = config.get("app_id", "")
    uu_id = uuid.uuid4()  # 随机生成的uuid数，为了每次都生成一个不重复的数。
    app_key = config.get("app_key", "")

    if not app_id or not app_key:
        raise ValueError("App ID and App Key must be configured in config.py")
    
    sign = hashlib.sha256(
        (app_id + input_text + str(uu_id) + str(time_curtime) + app_key).encode('utf-8')).hexdigest()  # sign生成

    data = {
        'q': translate_text,  # 翻译文本
        'appKey': app_id,  # 应用id
        'salt': uu_id,  # 随机生产的uuid码
        'sign': sign,  # 签名
        'signType': "v3",  # 签名类型，固定值
        'curtime': time_curtime,  # 秒级时间戳
    }
    if flag:
        data['from'] = "zh-CHS"  # 译文语种
        data['to'] = "en"  # 译文语种
    else:
        data['from'] = "en"  # 译文语种
        data['to'] = "zh-CHS"  # 译文语种
    try:
        r = requests.get(youdao_url, params=data).json()  # 获取返回的json()内容
    except Exception as e:
        r = {}
    
    translation_output = ''
    
    if not "translation" in r:
        error_code = r["errorCode"]
        logging.debug(f"error: {translate_text},error_code:{error_code}")
    else:
        translation_output = r["translation"][0]
        logging.debug(f"normal: {translate_text}")

    return translation_output

def translate_with_limit(input_list, limit=3, interval=2, progress_callback=None):
    output_list = []
    count = 0
    start_time = time.time()
    total = len(input_list)
    for index, phrase in enumerate(input_list):
        if count >= limit:
            elapsed_time = time.time() - start_time
            if elapsed_time < interval:
                time.sleep(interval - elapsed_time)
            count = 0
            start_time = time.time()

        translation = youdaoTranslate(phrase, 0)

        output_list.append(translation)
        count += 1

        # Update progress
        if progress_callback:
            progress = int((index + 1) / total * 100)
            progress_callback(progress)

    return output_list

def read_vocab_file(file_path):
    """
    Reads a text file where each line contains a word.
    Returns a set of these words for efficient searching.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        vocab = {line.strip().lower() for line in file}
    return vocab

def find_vocab_with_sentences(text, vocab):
    """
    Processes a given text, attempts to exclude potential proper nouns based on capitalization,
    finds vocabulary words in those sentences, and maps each word to the sentences it appears in.
    This version tries to avoid counting capitalized words as vocabulary unless they start a sentence.
    Returns a dictionary where keys are words and values are lists of sentences containing that word.
    """
    import re
    
    # Remove potential paragraph markers
    text = re.sub(r'\b[A-Z]\s+', '', text)
    
    # Split text into sentences
    sentences = re.split(r'[.!?]\s+', text)
    # Ensure each sentence ends with only one period
    sentences = [sentence.strip() + '.' if not sentence.endswith('.') else sentence.strip() for sentence in sentences if sentence]

    vocab_sentences = {}

    for sentence in sentences:
        # Extract words from sentence considering potential proper nouns
        words = re.findall(r'\b\w+\b', sentence)
        common_words = set(word.lower() for word in words if not (word[0].isupper() and sentence.index(word) != 0)) & vocab

        for word in common_words:
            if word not in vocab_sentences:
                vocab_sentences[word] = []
            vocab_sentences[word].append(sentence)

    return vocab_sentences

def process_vocab_sentences(vocab_sentences, progress_callback=None):
    sentence_to_words = {}
    for word, data in vocab_sentences.items():
        sentence = data[0]  # 获取每个单词的句子
        if sentence not in sentence_to_words:
            sentence_to_words[sentence] = [word]
        else:
            sentence_to_words[sentence].append(word)

    unique_sentences = list(sentence_to_words.keys())
    separator = " XYZSepMarkerXYZ. "
    chinese_separator = "XYZSepMarkerXYZ。"
    combined_sentences = separator.join(unique_sentences)
    
    # 已合并的句子长度
    MAX_LENGTH = 2000
    batch_sentences = []
    current_batch = []
    current_length = 0

    for sentence in unique_sentences:
        # 如果当前句子加上分隔符超过限制，则当前批次结束，开始新的批次
        if current_length + len(sentence) + len(separator) > MAX_LENGTH:
            batch_sentences.append(separator.join(current_batch))
            current_batch = [sentence]  # 开始新批次，包含当前句子
            current_length = len(sentence)
        else:
            current_batch.append(sentence)
            current_length += len(sentence) + len(separator)

    # 添加最后一个批次（如果有）
    if current_batch:
        batch_sentences.append(separator.join(current_batch))
        

    translated_batches = translate_with_limit(batch_sentences, progress_callback=progress_callback)
    
    # 将所有批次的翻译结果合并，并根据中文分隔符分割
    all_translated_text = chinese_separator.join(translated_batches)
    translated_sentences = all_translated_text.split(chinese_separator)

    if len(translated_sentences) != len(unique_sentences):
        raise ValueError("Mismatched number of sentences in translation. Check separator preservation.")

    for sentence, translation in zip(unique_sentences, translated_sentences):
        for word in sentence_to_words[sentence]:
            vocab_sentences[word] = {"original": sentence, "chinese_translate": translation.strip()}
    
    return vocab_sentences

def merge_translations(vocab_sentences):
    translated_sentence_to_words = {}
    for word, data in vocab_sentences.items():
        translation = data['chinese_translate']
        if translation not in translated_sentence_to_words:
            translated_sentence_to_words[translation] = [word]
        else:
            translated_sentence_to_words[translation].append(word)
    
    # 步骤2: 合并具有相同翻译句子的单词
    merged_vocab_sentences = {}
    for translation, words in translated_sentence_to_words.items():
        merged_key = ', '.join(words)  # 合并单词为一个字符串
        # 假设每个翻译都有一个对应的原始句子，这里我们取第一个单词的原始句子
        original_sentence = vocab_sentences[words[0]]['original']
        merged_vocab_sentences[merged_key] = {"original": original_sentence, "chinese_translate": translation}

    return merged_vocab_sentences

def main_process(text, vocab_file_path, progress_callback=None):
    vocab = read_vocab_file(vocab_file_path)
    vocab_sentences = find_vocab_with_sentences(text, vocab)
    processed_vocab_sentences = process_vocab_sentences(vocab_sentences, progress_callback)
    merged_vocab_sentences = merge_translations(processed_vocab_sentences)
    return merged_vocab_sentences

def test_process(text, vocab_file_path):
    vocab = read_vocab_file(vocab_file_path)
    vocab_sentences = find_vocab_with_sentences(text, vocab)
    return vocab_sentences