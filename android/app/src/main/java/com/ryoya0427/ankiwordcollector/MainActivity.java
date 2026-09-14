package com.ryoya0427.ankiwordcollector;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.Gravity;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.json.JSONObject;

public class MainActivity extends Activity {
    private static final int EXPORT_FILE = 9;
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private WordStore store;
    private NoteStore notes;
    private EditText input, meaning;
    private TextView status, count, list;
    private Spinner language, mode;
    private Button lookup, save, export;
    private final String[] languageNames = {"자동 감지", "영어", "일본어", "중국어", "스페인어", "프랑스어", "독일어", "러시아어", "아랍어", "힌디어"};
    private final String[] languageCodes = {"", "en", "ja", "zh-CN", "es", "fr", "de", "ru", "ar", "hi"};

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        try { store = new WordStore(this); notes = new NoteStore(new java.io.File(getFilesDir(), "anki/exam_notes.tsv")); } catch (Exception e) { Toast.makeText(this, "저장 준비 실패: " + e.getMessage(), Toast.LENGTH_LONG).show(); finish(); return; }
        LinearLayout layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL); layout.setPadding(32, 38, 32, 24);
        TextView title = label("Anki 단어 수집기", 22); layout.addView(title);
        mode = new Spinner(this); mode.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, new String[]{"단어·표현", "기사시험 개념 노트"})); layout.addView(mode);
        LinearLayout sourceRow = new LinearLayout(this); sourceRow.setGravity(Gravity.CENTER_VERTICAL); sourceRow.setPadding(0, 20, 0, 0);
        input = new EditText(this); input.setHint("단어·표현 입력"); input.setSingleLine(true); input.setImeOptions(EditorInfo.IME_ACTION_SEARCH);
        sourceRow.addView(input, new LinearLayout.LayoutParams(0, -2, 1));
        language = new Spinner(this); language.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, languageNames)); sourceRow.addView(language);
        layout.addView(sourceRow);
        lookup = new Button(this); lookup.setText("뜻 조회"); lookup.setOnClickListener(v -> lookup()); layout.addView(lookup);
        meaning = new EditText(this); meaning.setHint("한국어 뜻 (조회 실패 시 직접 입력)"); meaning.setMinLines(3); meaning.setGravity(Gravity.TOP); layout.addView(meaning);
        save = new Button(this); save.setText("저장"); save.setOnClickListener(v -> save()); layout.addView(save);
        status = label("조회하면 자동 저장됩니다.", 14); layout.addView(status);
        LinearLayout bottom = new LinearLayout(this); bottom.setGravity(Gravity.CENTER_VERTICAL); count = label("", 14); bottom.addView(count, new LinearLayout.LayoutParams(0, -2, 1));
        export = new Button(this); export.setText("TSV 내보내기"); export.setOnClickListener(v -> exportTsv()); bottom.addView(export); layout.addView(bottom);
        ScrollView scroll = new ScrollView(this); list = label("", 14); scroll.addView(list); layout.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
        mode.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            public void onNothingSelected(android.widget.AdapterView<?> parent) { }
            public void onItemSelected(android.widget.AdapterView<?> parent, android.view.View view, int position, long id) { updateMode(); }
        });
        setContentView(layout); updateMode();
    }
    private TextView label(String text, int size) { TextView view = new TextView(this); view.setText(text); view.setTextSize(size); return view; }
    private void lookup() {
        if (isNoteMode()) { save(); return; }
        String word = input.getText().toString().trim(); if (word.isEmpty()) { status.setText("단어 또는 표현을 입력하세요."); return; }
        status.setText("뜻 조회 중…"); String source = languageCodes[language.getSelectedItemPosition()]; if (source.isEmpty()) source = LanguageDetector.detect(word);
        final String finalSource = source;
        network.execute(() -> { try { String value = translate(word, finalSource); runOnUiThread(() -> { meaning.setText(value); save(); }); } catch (Exception e) { runOnUiThread(() -> status.setText("조회 실패: 직접 뜻을 입력한 뒤 저장하세요.")); } });
    }
    private String translate(String text, String source) throws Exception {
        String query = "q=" + URLEncoder.encode(text, "UTF-8") + "&langpair=" + URLEncoder.encode(source + "|ko", "UTF-8");
        HttpURLConnection connection = (HttpURLConnection) new URL("https://api.mymemory.translated.net/get?" + query).openConnection(); connection.setConnectTimeout(10000); connection.setReadTimeout(10000); connection.setRequestProperty("User-Agent", "AnkiWordCollector/1.0");
        byte[] bytes = connection.getInputStream().readAllBytes(); JSONObject data = new JSONObject(new String(bytes, StandardCharsets.UTF_8)); String value = data.getJSONObject("responseData").getString("translatedText");
        if (value.trim().isEmpty()) throw new Exception("empty"); return value;
    }
    private void save() {
        String word = input.getText().toString().trim(), value = meaning.getText().toString().trim(); if (word.isEmpty() || value.isEmpty()) { status.setText("단어와 뜻을 모두 입력하세요."); return; }
        try {
            if (isNoteMode()) { notes.add(word, value); status.setText("개념 노트를 저장했습니다."); }
            else { boolean added = store.addIfAbsent(word, value); status.setText(added ? "저장됨" : "이미 저장된 단어입니다."); }
            refresh();
        } catch (Exception e) { status.setText("저장 실패: " + e.getMessage()); }
    }
    private boolean isNoteMode() { return mode.getSelectedItemPosition() == 1; }
    private void updateMode() {
        boolean note = isNoteMode(); language.setVisibility(note ? android.view.View.GONE : android.view.View.VISIBLE);
        input.setHint(note ? "개념명 입력 (예: 정규화)" : "단어·표현 입력"); meaning.setHint(note ? "내 방식으로 개념 정리" : "한국어 뜻 (조회 실패 시 직접 입력)");
        lookup.setText(note ? "개념 저장" : "뜻 조회"); export.setText(note ? "개념 TSV 내보내기" : "TSV 내보내기"); status.setText(note ? "개념명과 정리를 입력해 저장하세요." : "조회하면 자동 저장됩니다."); refresh();
    }
    private void refresh() { boolean note = isNoteMode(); count.setText((note ? "저장된 개념: " + notes.count() : "저장된 단어: " + store.count()) + "개"); list.setText(note ? notes.list() : store.list()); }
    private void exportTsv() { Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT); intent.setType("text/tab-separated-values"); intent.putExtra(Intent.EXTRA_TITLE, isNoteMode() ? "exam_notes.tsv" : "anki_words.tsv"); startActivityForResult(intent, EXPORT_FILE); }
    @Override protected void onActivityResult(int request, int result, Intent data) { super.onActivityResult(request, result, data); if (request == EXPORT_FILE && result == RESULT_OK && data != null) try (OutputStream out = getContentResolver().openOutputStream(data.getData())) { out.write((isNoteMode() ? notes.text() : store.text()).getBytes(StandardCharsets.UTF_8)); status.setText("TSV를 내보냈습니다."); } catch (Exception e) { status.setText("내보내기 실패"); } }
    @Override protected void onDestroy() { network.shutdownNow(); super.onDestroy(); }
}
