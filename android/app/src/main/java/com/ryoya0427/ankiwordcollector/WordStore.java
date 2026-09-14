package com.ryoya0427.ankiwordcollector;

import android.content.Context;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.LinkedHashMap;
import java.util.Map;

public final class WordStore {
    private final File file;
    private final LinkedHashMap<String, String> rows = new LinkedHashMap<>();

    public WordStore(Context context) throws IOException {
        File directory = new File(context.getFilesDir(), "anki");
        if (!directory.exists() && !directory.mkdirs()) throw new IOException("저장 폴더를 만들 수 없습니다.");
        file = new File(directory, "anki_words.tsv");
        if (file.exists()) {
            for (String line : Files.readAllLines(file.toPath(), StandardCharsets.UTF_8)) {
                String[] fields = line.split("\\t", 2);
                if (fields.length == 2 && !fields[0].trim().isEmpty()) rows.put(fields[0].trim(), fields[1].trim());
            }
        }
    }
    public boolean addIfAbsent(String word, String meaning) throws IOException {
        String key = word.trim();
        if (rows.containsKey(key)) return false;
        rows.put(key, meaning.trim()); write(); return true;
    }
    public int count() { return rows.size(); }
    public String list() {
        StringBuilder result = new StringBuilder();
        for (Map.Entry<String, String> row : rows.entrySet()) result.append(row.getKey()).append("  ·  ").append(row.getValue()).append('\n');
        return result.toString();
    }
    public String text() {
        StringBuilder result = new StringBuilder();
        for (Map.Entry<String, String> row : rows.entrySet()) result.append(row.getKey()).append('\t').append(row.getValue()).append('\n');
        return result.toString();
    }
    private void write() throws IOException { Files.write(file.toPath(), text().getBytes(StandardCharsets.UTF_8)); }
}
