package com.ryoya0427.ankiwordcollector;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.LinkedHashMap;
import java.util.Map;

public final class NoteStore {
    private final File file;
    private final LinkedHashMap<String, String> rows = new LinkedHashMap<>();

    public NoteStore(File file) throws IOException {
        this.file = file;
        if (!file.exists()) return;
        for (String line : Files.readAllLines(file.toPath(), StandardCharsets.UTF_8)) {
            String[] fields = line.split("\\t", 2);
            if (fields.length == 2 && !fields[0].trim().isEmpty()) rows.put(fields[0].trim(), fields[1].trim());
        }
    }
    public void add(String concept, String explanation) throws IOException {
        rows.put(concept.trim(), explanation.trim());
        Files.write(file.toPath(), text().getBytes(StandardCharsets.UTF_8));
    }
    public int count() { return rows.size(); }
    public String text() {
        StringBuilder result = new StringBuilder();
        for (Map.Entry<String, String> row : rows.entrySet()) result.append(row.getKey()).append('\t').append(row.getValue()).append('\n');
        return result.toString();
    }
    public String list() { return text().replace('\t', ' ').replace('\n', '\n'); }
}
