VISION_SYSTEM = """Describe the image for an educational document. Return only the requested structured object.
Use the document language. Write 1-3 sentences describing educationally relevant content.
Choose exactly one kind: diagram, chart, table, formula, photo, decorative."""
TOPICS_SYSTEM = """Find meaningful topic boundaries in the supplied document paragraphs.
Return section titles in the document language. Each first_paragraph must be a
supplied paragraph number and numbers must be strictly increasing."""
