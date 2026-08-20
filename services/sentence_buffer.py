class SentenceBuffer:
    """
    Accumulates streaming text and emits complete
    sentences as they become available.
    """

    def __init__(self):
        self.buffer = ""

    def add(self, text):
        """
        Add a streaming text chunk.

        Returns a list of complete sentences that
        are ready to be spoken.
        """

        if not text:
            return []

        self.buffer += text

        sentences = []

        while True:

            boundary = self._find_boundary()

            if boundary is None:
                break

            sentence = self.buffer[:boundary].strip()

            self.buffer = self.buffer[boundary:]

            if sentence:
                sentences.append(sentence)

        return sentences

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
        Find the end of the first complete sentence.

        Returns the index immediately after the
        punctuation, or None if no complete sentence
        is available yet.
        """

        for index, character in enumerate(
            self.buffer
        ):

            if character not in ".!?":

                continue

            next_index = index + 1

            if next_index >= len(
                self.buffer
            ):

                return next_index

            next_character = (
                self.buffer[next_index]
            )

            if next_character.isspace():

                return next_index

        return None