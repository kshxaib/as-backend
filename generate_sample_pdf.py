import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def create_pdf(filename, title, questions):
    c = canvas.Canvas(filename, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, title)
    
    c.setFont("Helvetica", 12)
    y = 700
    for i, q in enumerate(questions, 1):
        if y < 100:
            c.showPage()
            c.setFont("Helvetica", 12)
            y = 750
        
        # Simple text wrapping for long questions
        words = q.split()
        lines = []
        current_line = f"Q{i}. "
        for word in words:
            if c.stringWidth(current_line + word, "Helvetica", 12) < 500:
                current_line += word + " "
            else:
                lines.append(current_line)
                current_line = "    " + word + " "
        lines.append(current_line)
        
        for line in lines:
            c.drawString(50, y, line)
            y -= 20
        y -= 10
        
    c.save()

# Questions for Paper 1 (2023)
paper1 = [
    "Perform Union, intersection, difference and complement over the fuzzy sets [Numerical Question] [10 Marks]",
    "List and explain fuzzification methods (membership methods) [5 Marks]",
    "Explain Markov decision process in detail [10 Marks]",
    "Explain Bayes Theorem [5 Marks]",
    "Explain Bayesian Belief Network with examples. Harry Burglar Alarm system [10 Marks]",
    "Differentiate between Fuzziness and Probability [5 Marks]"
]

# Questions for Paper 2 (2024) - Contains duplicates with slight variations
paper2 = [
    "Perform algebraic sum, algebraic product, bounded sum and bounded difference on fuzzy sets [Numerical Question] [10 Marks]",
    "What are fuzzification methods? Explain them in detail. [5 Marks]", # Similar to Q2 in Paper 1
    "List and explain defuzzification methods [5 Marks]",
    "State and explain Bayes Theorem with an example. [8 Marks]", # Similar to Q4 in Paper 1, diff marks
    "Explain centroid method of defuzzification [5 Marks]",
    "Explain advantages and disadvantages of cognitive system [5 Marks]",
    "What is the difference between Fuzziness and Probability? [6 Marks]" # Similar to Q6 in Paper 1
]

# Create PDFs
create_pdf("Sample_Paper_2023.pdf", "AI & Fuzzy Logic - Midterm 2023", paper1)
create_pdf("Sample_Paper_2024.pdf", "AI & Fuzzy Logic - Midterm 2024", paper2)

# Create a combined PDF
create_pdf("Combined_Sample_Papers.pdf", "AI & Fuzzy Logic - Combined Past Papers (2023-2024)", paper1 + paper2)

print("PDFs generated successfully.")
