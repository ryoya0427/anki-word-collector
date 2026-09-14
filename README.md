# Anki Word Collector

영어 단어와 표현을 한국어로 조회해 Anki용 TSV 파일에 자동 저장하는 Windows 프로그램입니다.

## 실행

`AnkiWordCollector_AutoSave.exe`를 실행하세요. Python 설치는 필요하지 않습니다.

영어 단어나 표현을 입력하고 Enter를 누르면 뜻이 표시되며, 같은 폴더의 `anki_words.tsv`에 자동 저장됩니다. 저장된 TSV 파일은 Anki의 **파일 → 가져오기**에서 탭 구분 파일로 불러올 수 있습니다.

## 번역

MyMemory의 공개 무료 API를 사용합니다. API 키는 포함하지 않으며, 자동 번역을 위해 입력한 영어가 해당 서비스로 전송됩니다.

인터넷 연결이나 번역 서비스 문제로 자동 조회가 실패하면 뜻을 직접 입력하고 Enter를 눌러 저장할 수 있습니다.

## 소스 실행

Python 3.10 이상에서 다음을 실행합니다.

```powershell
py anki_word_collector.py
```

추가 패키지는 필요하지 않습니다.
