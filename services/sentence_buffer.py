class SentenceBuffer:
    """
    Accumulates streaming text and emits natural,
    speakable phrases as they become available.
    """

    SENTENCE_BOUNDARIES = ".!?"
    PHRASE_BOUNDARIES = ",;:"
    MIN_PHRASE_LENGTH = 40

    def __init__(self):
        self.buffer = ""

    def add(self, text):
        """
        Add a streaming text chunk.

        Returns a list of complete sentences or
        natural phrases that are ready to be spoken.
        """

        if not text:
            return []

        self.buffer += text

        phrases = []

        while True:
            boundary = self._find_boundary()

            if boundary is None:
                break

            phrase = self.buffer[:boundary].strip()
            self.buffer = self.buffer[boundary:]

            if phrase:
                phrases.append(phrase)

        return phrases

    def flush(self):
        """
        Return any remaining text after streaming ends.
        """

        remaining = self.buffer.strip()
        self.buffer = ""

        if not remaining:
            return []

        return [remaining]

    def _find_boundary(self):
        """
        Find the end of the next natural speakable
        chunk.
        """

        for index, character in enumerate(self.buffer):
            if character in self.SENTENCE_BOUNDARIES:
                if self._is_sentence_boundary(index):
                    return index + 1

            if character in self.PHRASE_BOUNDARIES:
                if self._is_phrase_boundary(index):
                    return index + 1

        return None

    def _is_sentence_boundary(self, index):
        """
        Determine whether sentence punctuation marks
        a real sentence boundary.
        """

        character = self.buffer[index]

        if (
            character == "."
            and self._is_numeric_period(index)
        ):
            return False

        next_index = index + 1

        if next_index >= len(self.buffer):
            return True

        return self.buffer[next_index].isspace()

    def _is_phrase_boundary(self, index):
        """
        Allow phrase punctuation to emit only after
        enough text has accumulated.
        """

        if index + 1 < self.MIN_PHRASE_LENGTH:
            return False

        next_index = index + 1

        if next_index >= len(self.buffer):
            return True

        return self.buffer[next_index].isspace()

    def _is_numeric_period(self, index):
        """
        Protect decimal and version-number periods,
        such as 3.14 and Python 3.12.
        """

        previous_index = index - 1
        next_index = index + 1

        if previous_index < 0:
            return False

        if next_index >= len(self.buffer):
            return False

        return (
            self.buffer[previous_index].isdigit()
            and self.buffer[next_index].isdigit()
        )