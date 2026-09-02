from app.ai.personal_info_extractor import extract_personal_information


def test_extracts_explicit_personal_contact_block_from_cv_header():
    result = extract_personal_information(
        """CHEN ZHENGZHONG
chen.zhengzhong@example.com | +852 1234 5678
Location: Hong Kong
Address: 1 University Avenue, Sha Tin, Hong Kong
https://linkedin.com/in/chenzhengzhong | github.com/chenzhengzhong

EDUCATION
The Chinese University of Hong Kong
""",
        "cv.pdf",
    )

    assert result is not None
    assert result["category"] == "personal"
    assert result["confirmed"] is False
    assert result["source_file"] == "cv.pdf"
    assert "Name: CHEN ZHENGZHONG" in result["description"]
    assert "Email: chen.zhengzhong@example.com" in result["description"]
    assert "Phone: +852 1234 5678" in result["description"]
    assert "Location: Hong Kong" in result["description"]
    assert "Address: 1 University Avenue, Sha Tin, Hong Kong" in result["description"]
    assert "LinkedIn: https://linkedin.com/in/chenzhengzhong" in result["description"]
    assert "GitHub: github.com/chenzhengzhong" in result["description"]


def test_extracts_a_labelled_name_without_repeating_the_label():
    result = extract_personal_information(
        """Name: Chen Zhengzhong
Email: chen.zhengzhong@example.com
Phone: +852 1234 5678

EDUCATION
Example University
""",
        "cv.pdf",
    )

    assert result is not None
    assert result["title"] == "Chen Zhengzhong"
    assert "Name: Chen Zhengzhong" in result["description"]
    assert "Name: Name:" not in result["description"]


def test_does_not_invent_personal_details_when_contact_block_is_missing():
    result = extract_personal_information(
        """EDUCATION
The Chinese University of Hong Kong
BSc in Mathematics
""",
        "cv.pdf",
    )

    assert result is None


def test_does_not_mistake_degree_description_for_a_name():
    result = extract_personal_information(
        """Computer Science Student
student@example.com | +852 1234 5678

EDUCATION
Example University
""",
        "cv.pdf",
    )

    assert result is not None
    assert result["title"] == "Personal information"
    assert "Name: Computer Science Student" not in result["description"]


def test_extracts_conventional_unlabelled_cv_header_address():
    result = extract_personal_information(
        """Zeon Chen Zhengzhong (陳政中)
Room 220, Madam S. H. Ho Hall, Chung Chi College,
Shatin, Hong Kong SAR, China
Phone: (+852) 64061561 Email: zhengzhongchen2@example.com
GitHub: https://github.com/ChanChengChung
LinkedIn: https://www.linkedin.com/in/zhengzhong-chen-bbb764309/
EDUCATION
The Chinese University of Hong Kong
""",
        "cv.pdf",
    )

    assert result is not None
    assert result["title"] == "Zeon Chen Zhengzhong (陳政中)"
    assert (
        "Address: Room 220, Madam S. H. Ho Hall, Chung Chi College, Shatin, Hong Kong SAR, China"
        in result["description"]
    )
    assert "Location: Shatin, Hong Kong SAR, China" in result["description"]
