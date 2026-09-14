package com.ryoya0427.ankiwordcollector;

import static org.junit.Assert.assertEquals;

import org.junit.Test;
import java.io.File;
import java.nio.file.Files;

public class LanguageDetectorTest {
    @Test public void detectsJapaneseCharacters() {
        assertEquals("ja", LanguageDetector.detect("こんにちは"));
    }

    @Test public void treatsHanOnlyInputAsChineseUntilUserChoosesJapanese() {
        assertEquals("zh-CN", LanguageDetector.detect("漢字"));
    }

    @Test public void savesExamConceptAsTabSeparatedNote() throws Exception {
        File file = Files.createTempFile("exam-notes", ".tsv").toFile();
        file.delete();
        NoteStore notes = new NoteStore(file);
        notes.add("정규화", "데이터 중복을 줄이는 설계 과정");
        assertEquals("정규화\t데이터 중복을 줄이는 설계 과정\n", notes.text());
    }
}
