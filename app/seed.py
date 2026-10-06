import random

from .extensions import db
from .models import User, Subject, Lesson, Exercise, Test

SUBJECTS = [
    "Toán", "Ngữ văn", "Tiếng Anh", "Vật lý", "Hóa học",
    "Sinh học", "Lịch sử", "Địa lý", "Giáo dục công dân"
]

CURRICULUM = {
    6: {
        "Toán": [
            "Tập hợp và cách ghi tập hợp",
            "Tập hợp số tự nhiên",
            "Phép cộng và phép trừ số tự nhiên",
            "Phép nhân, phép chia và lũy thừa",
            "Tính chia hết và số nguyên tố",
            "Ước chung, bội chung, ƯCLN và BCNN",
            "Số nguyên",
            "Phân số",
            "Hình học trực quan và các hình phẳng cơ bản",
            "Chu vi, diện tích và dữ liệu thống kê ban đầu",
        ],
        "Ngữ văn": [
            "Truyện đồng thoại và bài học cuộc sống",
            "Thơ lục bát và cảm xúc tuổi thơ",
            "Kể lại trải nghiệm bản thân",
            "Văn bản thông tin gần gũi đời sống",
            "Miêu tả người và cảnh vật",
            "Nói và nghe trong giao tiếp học đường",
        ],
        "Tiếng Anh": [
            "My new school",
            "My house and daily routines",
            "Friends and personalities",
            "My neighbourhood",
            "Natural wonders of the world",
            "Our Tet holiday",
        ],
        "Vật lý": [
            "Đo độ dài, khối lượng và thời gian",
            "Lực và tác dụng của lực",
            "Chuyển động và tốc độ",
            "Năng lượng trong đời sống",
            "Nhiệt và sự truyền nhiệt",
        ],
        "Hóa học": [
            "Chất và tính chất của chất",
            "Một số vật liệu, nguyên liệu và nhiên liệu",
            "Không khí và vai trò của oxi",
            "Nước và dung dịch trong đời sống",
        ],
        "Sinh học": [
            "Tế bào – đơn vị cơ sở của sự sống",
            "Cơ thể sống và các cấp tổ chức",
            "Đa dạng sinh vật",
            "Môi trường sống và thích nghi",
        ],
        "Lịch sử": [
            "Lịch sử và cuộc sống",
            "Xã hội nguyên thủy",
            "Các quốc gia cổ đại phương Đông",
            "Các quốc gia cổ đại phương Tây",
            "Văn minh Ai Cập, Lưỡng Hà, Ấn Độ, Trung Hoa",
            "Bước đầu lịch sử Việt Nam cổ đại",
        ],
        "Địa lý": [
            "Bản đồ và phương hướng",
            "Trái Đất trong hệ Mặt Trời",
            "Chuyển động của Trái Đất",
            "Cấu tạo Trái Đất và địa hình",
            "Thời tiết và khí hậu",
            "Sông ngòi, hồ, biển và sinh vật",
        ],
        "Giáo dục công dân": [
            "Tự hào về truyền thống gia đình, dòng họ",
            "Yêu thương con người",
            "Siêng năng, kiên trì",
            "Tôn trọng sự thật",
            "Tự lập và tự chăm sóc bản thân",
            "Ứng xử văn minh nơi công cộng",
        ],
    },
    7: {
        "Toán": [
            "Số hữu tỉ",
            "Số thực",
            "Tỉ lệ thức và đại lượng tỉ lệ",
            "Biểu thức đại số và đa thức một biến",
            "Quan hệ giữa các yếu tố trong tam giác",
            "Tam giác bằng nhau",
            "Quan hệ vuông góc và song song",
            "Một số hình khối trong thực tiễn",
            "Thống kê và xác suất thực nghiệm",
        ],
        "Ngữ văn": [
            "Truyện ngắn hiện đại",
            "Thơ bốn chữ và năm chữ",
            "Tùy bút, tản văn",
            "Nghị luận về một vấn đề đời sống",
            "Viết bài văn biểu cảm",
            "Thảo luận và trình bày ý kiến",
        ],
        "Tiếng Anh": [
            "Hobbies and healthy living",
            "Community service",
            "Music and movies",
            "Food and drinks",
            "Transport and traffic",
            "Festivals around the world",
        ],
        "Vật lý": [
            "Ánh sáng và sự phản xạ ánh sáng",
            "Gương phẳng và ảnh tạo bởi gương",
            "Âm thanh và nguồn âm",
            "Độ cao, độ to, môi trường truyền âm",
            "Điện tích và dòng điện ban đầu",
        ],
        "Hóa học": [
            "Nguyên tử và phân tử ở mức khái quát",
            "Nguyên tố hóa học gần gũi",
            "Hợp chất thông dụng trong đời sống",
            "Sự biến đổi của chất quanh em",
        ],
        "Sinh học": [
            "Trao đổi chất và chuyển hóa năng lượng",
            "Sinh trưởng và phát triển ở sinh vật",
            "Cảm ứng ở sinh vật",
            "Sinh sản ở sinh vật",
        ],
        "Lịch sử": [
            "Sự hình thành xã hội phong kiến",
            "Trung Quốc thời phong kiến",
            "Ấn Độ và Đông Nam Á thời phong kiến",
            "Châu Âu trung đại",
            "Việt Nam từ thế kỉ X đến XV",
            "Văn hóa và bảo vệ di sản",
        ],
        "Địa lý": [
            "Dân số và phân bố dân cư",
            "Đô thị hóa và quần cư",
            "Các châu lục và đại dương",
            "Châu Á – đặc điểm tự nhiên và dân cư",
            "Châu Âu – tự nhiên và kinh tế xã hội",
            "Bảo vệ môi trường địa phương",
        ],
        "Giáo dục công dân": [
            "Tự giác và trách nhiệm",
            "Quản lí thời gian hiệu quả",
            "Đoàn kết, tương trợ",
            "Giữ chữ tín",
            "Ứng phó với bạo lực học đường",
            "Phòng chống tệ nạn xã hội",
        ],
    },
    8: {
        "Toán": [
            "Đơn thức và đa thức nhiều biến",
            "Hằng đẳng thức đáng nhớ",
            "Phân tích đa thức thành nhân tử",
            "Phân thức đại số",
            "Phương trình bậc nhất một ẩn",
            "Hàm số và đồ thị",
            "Tứ giác và các hình đặc biệt",
            "Diện tích đa giác",
            "Thống kê và xác suất",
        ],
        "Ngữ văn": [
            "Truyện lịch sử và truyện hiện thực",
            "Thơ trào phúng và thơ yêu nước",
            "Văn bản nghị luận trung đại và hiện đại",
            "Thuyết minh về một hiện tượng, một danh lam",
            "Viết văn nghị luận xã hội đơn giản",
            "Nói và nghe theo chủ đề xã hội",
        ],
        "Tiếng Anh": [
            "Leisure activities",
            "Life in the countryside",
            "Peoples of Viet Nam",
            "Our customs and traditions",
            "Festivals in Viet Nam",
            "Natural disasters and communication",
        ],
        "Vật lý": [
            "Áp suất và áp suất chất lỏng",
            "Lực đẩy Ác-si-mét",
            "Công cơ học và công suất",
            "Cơ năng",
            "Nhiệt năng và sự bảo toàn năng lượng",
        ],
        "Hóa học": [
            "Chất nguyên chất và hỗn hợp",
            "Nguyên tử, nguyên tố hóa học và đơn chất, hợp chất",
            "Phản ứng hóa học",
            "Mol và tính theo phương trình hóa học",
            "Dung dịch và nồng độ dung dịch",
            "Axit, bazơ, muối",
        ],
        "Sinh học": [
            "Cấu tạo và chức năng cơ thể người",
            "Vận động",
            "Tuần hoàn, hô hấp",
            "Tiêu hóa và chuyển hóa",
            "Bài tiết và cân bằng nội môi",
            "Thần kinh và giác quan",
        ],
        "Lịch sử": [
            "Các cuộc cách mạng tư sản",
            "Cách mạng công nghiệp và biến đổi xã hội",
            "Việt Nam từ thế kỉ XVI đến XVIII",
            "Phong trào Tây Sơn",
            "Việt Nam nửa đầu thế kỉ XIX",
            "Kháng chiến chống ngoại xâm cuối thế kỉ XIX",
        ],
        "Địa lý": [
            "Việt Nam – vị trí địa lí và phạm vi lãnh thổ",
            "Địa hình Việt Nam",
            "Khí hậu Việt Nam",
            "Sông ngòi, đất, sinh vật Việt Nam",
            "Biển đảo Việt Nam",
            "Thiên tai và bảo vệ thiên nhiên",
        ],
        "Giáo dục công dân": [
            "Lao động cần cù, sáng tạo",
            "Tôn trọng và học hỏi các dân tộc khác",
            "Bảo vệ lẽ phải",
            "Tôn trọng tài sản của người khác",
            "Phòng ngừa tai nạn và tệ nạn",
            "Quyền và nghĩa vụ cơ bản của công dân",
        ],
    },
    9: {
        "Toán": [
            "Căn thức và hệ thức lượng trong tam giác vuông",
            "Hàm số bậc nhất",
            "Hệ phương trình bậc nhất hai ẩn",
            "Phương trình bậc hai một ẩn",
            "Hệ thức Vi-ét và ứng dụng",
            "Đường tròn",
            "Góc với đường tròn",
            "Hình trụ, hình nón, hình cầu",
            "Thống kê và xác suất",
        ],
        "Ngữ văn": [
            "Truyện hiện đại Việt Nam",
            "Thơ hiện đại Việt Nam",
            "Nghị luận xã hội và nghị luận văn học",
            "Văn bản thông tin và nhật dụng",
            "Viết bài văn nghị luận hoàn chỉnh",
            "Nói và nghe định hướng thi chuyển cấp",
        ],
        "Tiếng Anh": [
            "Local environment",
            "City life",
            "Teen stress and pressure",
            "Life in the past",
            "Wonders of Viet Nam",
            "English in the world",
        ],
        "Vật lý": [
            "Điện học",
            "Định luật Ôm",
            "Công và công suất điện",
            "Điện từ học",
            "Quang học",
            "Sự bảo toàn và chuyển hóa năng lượng",
        ],
        "Hóa học": [
            "Tính chất của kim loại",
            "Dãy hoạt động hóa học của kim loại",
            "Nhôm, sắt và hợp kim",
            "Phi kim và hợp chất của phi kim",
            "Hiđrocacbon",
            "Dẫn xuất hiđrocacbon đơn giản",
        ],
        "Sinh học": [
            "Di truyền và biến dị",
            "Nhiễm sắc thể và ADN",
            "Quy luật Menđen",
            "Biến dị",
            "Sinh vật và môi trường",
            "Hệ sinh thái và bảo vệ môi trường",
        ],
        "Lịch sử": [
            "Thế giới từ sau 1945",
            "Chiến tranh lạnh",
            "Cách mạng khoa học – kĩ thuật",
            "Việt Nam 1919–1930",
            "Việt Nam 1930–1945",
            "Việt Nam từ 1945 đến 2000",
        ],
        "Địa lý": [
            "Dân cư và lao động Việt Nam",
            "Chuyển dịch cơ cấu kinh tế",
            "Địa lí nông nghiệp",
            "Địa lí công nghiệp",
            "Dịch vụ và giao thông",
            "Các vùng kinh tế Việt Nam",
        ],
        "Giáo dục công dân": [
            "Chí công vô tư",
            "Tự chủ và dân chủ",
            "Bảo vệ hòa bình",
            "Hợp tác cùng phát triển",
            "Sống có đạo đức và tuân theo pháp luật",
            "Quyền tham gia quản lí nhà nước và xã hội",
        ],
    },
    10: {
        "Toán": ["Mệnh đề và tập hợp","Bất phương trình và hệ bất phương trình bậc nhất hai ẩn","Hàm số và đồ thị","Hệ thức lượng trong tam giác","Vectơ","Thống kê","Xác suất"],
        "Ngữ văn": ["Sức hấp dẫn của truyện kể","Vẻ đẹp của thơ ca","Nghệ thuật thuyết phục trong văn bản nghị luận","Viết văn bản nghị luận xã hội","Viết văn bản thông tin","Nói và nghe theo chủ đề"],
        "Tiếng Anh": ["Family life and lifestyle","Humans and the environment","Music and media","For a better community","Inventions and education","Gender equality and career paths"],
        "Vật lý": ["Mở đầu về Vật lí","Động học","Động lực học","Năng lượng, công, công suất","Động lượng","Chuyển động tròn","Biến dạng của vật rắn"],
        "Hóa học": ["Cấu tạo nguyên tử","Bảng tuần hoàn các nguyên tố hóa học","Liên kết hóa học","Phản ứng oxi hóa – khử","Năng lượng hóa học","Tốc độ phản ứng và cân bằng hóa học"],
        "Sinh học": ["Giới thiệu Sinh học và các cấp độ tổ chức sống","Thành phần hóa học của tế bào","Cấu trúc tế bào","Trao đổi chất qua màng và chuyển hóa vật chất","Chu kì tế bào và phân bào","Vi sinh vật và virus"],
        "Lịch sử": ["Lịch sử và sử học","Các nền văn minh thế giới cổ - trung đại","Các cuộc cách mạng công nghiệp","Lịch sử Đông Nam Á","Việt Nam từ nguồn gốc đến thế kỉ X","Việt Nam từ thế kỉ X đến thế kỉ XIX"],
        "Địa lý": ["Bản đồ","Trái Đất và hệ quả chuyển động của Trái Đất","Khí quyển và thời tiết khí hậu","Thủy quyển và sinh quyển","Địa lí dân cư","Cơ cấu nền kinh tế"],
        "Giáo dục công dân": ["Những vấn đề chung của pháp luật","Thực hiện pháp luật","Quyền bình đẳng của công dân","Cơ chế thị trường","Ngân sách và tiêu dùng thông minh","Đạo đức, trách nhiệm và cộng đồng"],
    },
    11: {
        "Toán": ["Hàm số lượng giác và phương trình lượng giác","Dãy số, cấp số cộng, cấp số nhân","Giới hạn và hàm số liên tục","Hàm số mũ và hàm số lôgarit","Đạo hàm","Quan hệ song song trong không gian","Quan hệ vuông góc trong không gian","Xác suất"],
        "Ngữ văn": ["Truyện hiện đại và góc nhìn đời sống","Thơ trữ tình hiện đại","Kí và phóng sự","Nghị luận văn học","Nghị luận xã hội nâng cao","Viết, nói và nghe học thuật"],
        "Tiếng Anh": ["Generation gap","Healthy living","Global warming","ASEAN and global issues","Further education","The world of work"],
        "Vật lý": ["Điện trường","Dòng điện không đổi","Từ trường","Cảm ứng điện từ","Khúc xạ ánh sáng","Mắt và các dụng cụ quang học"],
        "Hóa học": ["Cân bằng hóa học trong dung dịch","Nitrogen - phosphorus","Carbon - silicon","Đại cương hóa học hữu cơ","Hydrocarbon","Dẫn xuất halogen - alcohol - phenol"],
        "Sinh học": ["Trao đổi nước và khoáng ở thực vật","Quang hợp","Hô hấp ở thực vật","Cảm ứng và sinh trưởng phát triển ở thực vật","Sinh học cơ thể động vật","Cảm ứng ở động vật"],
        "Lịch sử": ["Thế giới cận đại","Các nước tư bản chuyển sang đế quốc chủ nghĩa","Phong trào công nhân và chủ nghĩa xã hội","Chiến tranh thế giới thứ nhất","Việt Nam nửa sau thế kỉ XIX đến đầu thế kỉ XX","Phong trào yêu nước đầu thế kỉ XX"],
        "Địa lý": ["Địa lí kinh tế thế giới","Nông nghiệp","Công nghiệp","Dịch vụ","Toàn cầu hóa và khu vực hóa","Liên kết vùng và phát triển bền vững"],
        "Giáo dục công dân": ["Công dân với kinh tế","Công dân với đạo đức","Công dân với pháp luật","Quyền và nghĩa vụ công dân","Kĩ năng ra quyết định tài chính","Trách nhiệm xã hội"],
    },
    12: {
        "Toán": ["Ứng dụng đạo hàm để khảo sát và vẽ đồ thị hàm số","Vectơ và hệ trục tọa độ trong không gian","Nguyên hàm - tích phân","Số phức","Khối đa diện và thể tích khối đa diện","Mặt nón, mặt trụ, mặt cầu","Xác suất thống kê"],
        "Ngữ văn": ["Văn học Việt Nam hiện đại","Văn học nước ngoài hiện đại","Nghị luận xã hội chuyên sâu","Nghị luận văn học tổng hợp","Viết bài theo định hướng thi tốt nghiệp","Nói và nghe học thuật"],
        "Tiếng Anh": ["Life stories and identity","Urbanisation and green living","Artificial intelligence and future jobs","Cultural diversity","Global citizenship","Revision for graduation exam"],
        "Vật lý": ["Dao động cơ","Sóng cơ","Dòng điện xoay chiều","Sóng điện từ","Lượng tử ánh sáng","Hạt nhân nguyên tử"],
        "Hóa học": ["Este - lipid","Carbohydrate","Amin - amino acid - protein","Polymer","Kim loại và hợp kim","Điện hóa học và ăn mòn kim loại"],
        "Sinh học": ["Cơ chế di truyền và biến dị","Quy luật di truyền","Di truyền quần thể","Ứng dụng di truyền học","Tiến hóa","Sinh thái học"],
        "Lịch sử": ["Quan hệ quốc tế sau Chiến tranh thế giới thứ hai","Liên Xô và Đông Âu","Mĩ, Tây Âu, Nhật Bản","Đông Nam Á và thế giới sau 1945","Lịch sử Việt Nam 1919-1945","Lịch sử Việt Nam 1945-2000"],
        "Địa lý": ["Việt Nam trên đường đổi mới","Địa lí tự nhiên Việt Nam","Dân cư và lao động","Chuyển dịch cơ cấu kinh tế","Các ngành kinh tế","Các vùng kinh tế"],
        "Giáo dục công dân": ["Pháp luật với tự do và dân chủ","Pháp luật với phát triển kinh tế","Quyền con người và quyền công dân","Công dân với hội nhập","Đạo đức nghề nghiệp","Trách nhiệm công dân trong kỉ nguyên số"],
    },
}

SUBJECT_FOCUS = {
    "Toán": ["khái niệm", "quy tắc", "tính chất", "ví dụ", "vận dụng"],
    "Ngữ văn": ["đọc hiểu", "nghệ thuật", "nội dung", "thông điệp", "viết đoạn"],
    "Tiếng Anh": ["từ vựng", "ngữ pháp", "phát âm", "giao tiếp", "viết câu"],
    "Vật lý": ["hiện tượng", "định luật", "công thức", "thí nghiệm", "vận dụng"],
    "Hóa học": ["chất", "tính chất", "phản ứng", "nhận biết", "ứng dụng"],
    "Sinh học": ["cấu tạo", "chức năng", "quá trình", "vai trò", "mối liên hệ"],
    "Lịch sử": ["bối cảnh", "diễn biến", "nhân vật", "kết quả", "ý nghĩa"],
    "Địa lý": ["đặc điểm", "phân bố", "nguyên nhân", "hệ quả", "thực tiễn"],
    "Giáo dục công dân": ["khái niệm", "biểu hiện", "ý nghĩa", "cách thực hiện", "tình huống"],
}

def gen_questions(subject, grade, chapter, topic, count=8, label=None):
    focus_keywords = SUBJECT_FOCUS.get(subject, ["kiến thức", "dấu hiệu", "vận dụng", "ghi nhớ", "ứng dụng"])
    topic_slug = (topic or "nội dung ôn tập").lower()
    stem_templates = {
        "Toán": [
            f"Phát biểu nào đúng nhất về chủ đề {topic_slug}?",
            f"Trong các lựa chọn sau, bước làm nào phù hợp nhất với dạng toán {topic_slug}?",
            f"Nhận xét nào đúng về tính chất quan trọng của {topic_slug}?",
            f"Ví dụ nào minh họa đúng cho kiến thức {topic_slug}?",
        ],
        "Ngữ văn": [
            f"Ý nào nêu đúng nội dung chính của chủ đề {topic_slug}?",
            f"Đặc điểm nghệ thuật nào phù hợp nhất với chủ đề {topic_slug}?",
            f"Thông điệp nào bám sát nội dung bài học {topic_slug}?",
            f"Cách triển khai nào đúng khi viết về chủ đề {topic_slug}?",
        ],
        "Tiếng Anh": [
            f"Lựa chọn nào đúng nhất khi sử dụng từ vựng thuộc chủ đề {topic_slug}?",
            f"Mẫu câu nào phù hợp nhất với nội dung {topic_slug}?",
            f"Đáp án nào đúng về ngữ pháp trong bài {topic_slug}?",
            f"Phản hồi nào phù hợp trong tình huống giao tiếp về {topic_slug}?",
        ],
        "Vật lý": [
            f"Hiện tượng nào mô tả đúng nội dung của {topic_slug}?",
            f"Kết luận nào đúng khi vận dụng kiến thức {topic_slug}?",
            f"Đại lượng hoặc công thức nào gắn đúng với {topic_slug}?",
            f"Thí nghiệm nào phù hợp để kiểm chứng kiến thức {topic_slug}?",
        ],
        "Hóa học": [
            f"Nhận định nào đúng về nội dung {topic_slug}?",
            f"Tính chất nào phù hợp nhất với chủ đề {topic_slug}?",
            f"Phản ứng nào gần đúng nhất với kiến thức {topic_slug}?",
            f"Ứng dụng nào bám sát chủ đề {topic_slug}?",
        ],
        "Sinh học": [
            f"Cấu tạo hoặc quá trình nào gắn đúng với {topic_slug}?",
            f"Chức năng nào phù hợp nhất với nội dung {topic_slug}?",
            f"Mối liên hệ nào đúng trong chủ đề {topic_slug}?",
            f"Nhận định nào phản ánh đúng kiến thức {topic_slug}?",
        ],
        "Lịch sử": [
            f"Đâu là nội dung đúng về chủ đề lịch sử {topic_slug}?",
            f"Yếu tố nào thể hiện đúng bối cảnh của {topic_slug}?",
            f"Kết quả hoặc ý nghĩa nào gắn sát với {topic_slug}?",
            f"Nhân vật hoặc sự kiện nào liên hệ đúng với {topic_slug}?",
        ],
        "Địa lý": [
            f"Đặc điểm nào phản ánh đúng nội dung {topic_slug}?",
            f"Nguyên nhân nào phù hợp nhất với chủ đề {topic_slug}?",
            f"Hệ quả nào thường gặp trong bài {topic_slug}?",
            f"Nhận định thực tiễn nào đúng về {topic_slug}?",
        ],
        "Giáo dục công dân": [
            f"Biểu hiện nào đúng với chủ đề {topic_slug}?",
            f"Cách ứng xử nào phù hợp với nội dung {topic_slug}?",
            f"Ý nghĩa nào bám sát bài học {topic_slug}?",
            f"Tình huống nào cần vận dụng đúng kiến thức {topic_slug}?",
        ],
    }
    stems = stem_templates.get(subject, [f"Nhận định nào đúng nhất về {topic_slug}?"])
    option_sets = [
        [
            f"Nêu đúng {focus_keywords[0]} và yêu cầu trọng tâm của {topic_slug}",
            f"Nêu gần đúng nhưng thiếu ý về {focus_keywords[1]} trong {topic_slug}",
            f"Hiểu sai bản chất của {topic_slug}",
            f"Không liên quan trực tiếp tới {topic_slug}",
        ],
        [
            f"Vận dụng hợp lý kiến thức {topic_slug} vào tình huống quen thuộc",
            f"Vận dụng được một phần nhưng bỏ sót bước quan trọng",
            f"Chọn cách làm dễ nhầm lẫn với chủ đề khác",
            f"Đưa ra kết luận trái với kiến thức {topic_slug}",
        ],
        [
            f"Gắn đúng {topic_slug} với nội dung {focus_keywords[2]}",
            f"Nhắc đến {topic_slug} nhưng diễn đạt chưa đầy đủ",
            f"Lẫn lộn {topic_slug} với một chủ đề khác",
            f"Nêu thông tin không thuộc phạm vi bài học",
        ],
    ]
    questions = []
    for i in range(1, count + 1):
        options = random.choice(option_sets)
        answer = random.choice(["A", "B", "C", "D"])
        correct_idx = ["A", "B", "C", "D"].index(answer)
        if correct_idx != 0:
            options = options.copy()
            options[0], options[correct_idx] = options[correct_idx], options[0]
        question_label = f"{label} - " if label else ""
        questions.append({
            "question": f"Câu {i}: {question_label}{subject} lớp {grade}, chương {chapter}. {random.choice(stems)}",
            "options": options,
            "answer": answer,
        })
    return questions

def create_user_if_missing(full_name, email, password, role, grade_level=None, class_name=None):
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(full_name=full_name, email=email, role=role, grade_level=grade_level, class_name=class_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

def build_lesson_content(subject, grade, chapter, topic):
    focus = SUBJECT_FOCUS.get(subject, ["kiến thức", "ví dụ", "vận dụng", "mở rộng", "ôn tập"])
    return (
        f"{subject} lớp {grade} - Chương {chapter}: {topic}\n\n"
        "1. Mục tiêu học tập\n"
        f"- Nắm được nội dung cốt lõi của chủ đề {topic}.\n"
        f"- Biết trình bày rõ các ý chính liên quan đến {focus[0]}, {focus[1]} và {focus[2]}.\n"
        "- Biết vận dụng kiến thức vào câu hỏi cơ bản và bài tập ngắn.\n\n"
        "2. Nội dung trọng tâm\n"
        f"- Khái quát chủ đề: {topic}.\n"
        f"- Làm rõ các điểm cần nhớ về {focus[0]} và {focus[1]}.\n"
        f"- Phân biệt đúng sai, nhận diện lỗi thường gặp trong phần {focus[2]}.\n"
        f"- Gắn chủ đề với {focus[3]} trong học tập hoặc đời sống.\n\n"
        "3. Ví dụ và định hướng luyện tập\n"
        "- Xem một ví dụ mẫu có lời giải hoặc hướng dẫn ngắn.\n"
        "- Ghi lại 3 từ khóa hoặc ý chính quan trọng nhất.\n"
        "- Tự giải thích lại bằng lời của mình để kiểm tra mức độ hiểu bài.\n\n"
        "4. Ghi nhớ nhanh\n"
        "- Học theo sơ đồ hoặc gạch đầu dòng.\n"
        "- Làm bài từ mức nhận biết đến vận dụng.\n"
        "- So sánh với các bài/chủ đề gần giống để tránh nhầm lẫn.\n"
    )

def build_exercise_content(subject, grade, chapter, topic):
    return (
        f"Bài tập luyện tập {subject} lớp {grade} - Chương {chapter}: {topic}\n\n"
        "Phần A. Nhận biết\n"
        f"- Bài 1: Nêu lại khái niệm hoặc ý chính của chủ đề {topic}.\n"
        f"- Bài 2: Chỉ ra dấu hiệu/đặc điểm đúng của {topic}.\n\n"
        "Phần B. Thông hiểu\n"
        f"- Bài 3: Giải thích vì sao một ví dụ thuộc hoặc không thuộc chủ đề {topic}.\n"
        f"- Bài 4: So sánh {topic} với kiến thức đã học ở bài gần nhất.\n\n"
        "Phần C. Vận dụng\n"
        f"- Bài 5: Giải quyết một tình huống ngắn gắn với {topic}.\n"
        f"- Bài 6: Tự nêu cách làm hoặc viết đoạn trình bày kết quả.\n"
    )

def build_answer_key(subject, topic):
    return (
        f"Gợi ý đáp án cho {subject} - {topic}:\n"
        "- Xác định đúng từ khóa và yêu cầu của câu hỏi.\n"
        "- Trình bày rõ ràng, có bước hoặc có luận điểm ngắn gọn.\n"
        "- Dùng ví dụ minh họa nếu đề yêu cầu.\n"
        "- Kết luận chính xác, không lan man.\n"
    )

def upsert_lesson(subject_id, grade, chapter, title, content):
    item = Lesson.query.filter_by(subject_id=subject_id, grade_level=grade, chapter=chapter).first()
    if not item:
        item = Lesson(subject_id=subject_id, grade_level=grade, chapter=chapter, title=title, content=content)
        db.session.add(item)

def upsert_exercise(subject_id, grade, chapter, title, content, answer_key):
    item = Exercise.query.filter_by(subject_id=subject_id, grade_level=grade, chapter=chapter).first()
    if not item:
        item = Exercise(subject_id=subject_id, grade_level=grade, chapter=chapter, title=title, content=content, answer_key=answer_key)
        db.session.add(item)

def upsert_test(subject_id, grade, chapter, title, instructions, answer_key, question_bank):
    item = Test.query.filter_by(subject_id=subject_id, grade_level=grade, chapter=chapter, test_type="chapter").first()
    if not item:
        item = Test(
            subject_id=subject_id,
            grade_level=grade,
            chapter=chapter,
            test_type="chapter",
            title=title,
            instructions=instructions,
            answer_key=answer_key,
        )
        item.set_question_bank([])          # bank rỗng, chờ tools/build_bank.py sinh bằng AI
        item.review_status = "draft"
        db.session.add(item)

def upsert_term_test(subject_id, grade, test_type, label, subject_name, topics):
    item = Test.query.filter_by(subject_id=subject_id, grade_level=grade, chapter=None, test_type=test_type).first()
    if item:
        return                                # đã có thì giữ nguyên, không ghi đè
    item = Test(
        subject_id=subject_id, grade_level=grade, chapter=None, test_type=test_type,
        title=f"{label} - {subject_name} lớp {grade}",
        instructions=f"Bài kiểm tra {label.lower()} gồm 30 câu trắc nghiệm bám sát nội dung đã học của môn {subject_name}.",
        answer_key="Tự động chấm bằng đáp án trong ngân hàng câu hỏi.",
        review_status="draft",
    )
    item.set_question_bank([])                # sẽ ghép từ đề chương đã duyệt
    db.session.add(item)


def seed_data():
    if not Subject.query.first():
        for name in SUBJECTS:
            db.session.add(Subject(name=name))
        db.session.commit()

    create_user_if_missing("Teacher Demo", "teacher@example.com", "teacher123", "teacher")
    create_user_if_missing("Admin Demo", "admin@example.com", "admin123", "admin")
    create_user_if_missing("Student Demo", "student@example.com", "student123", "student", 10, "10A1")

    subjects = Subject.query.all()
    for grade in range(6, 13):
        for subject in subjects:
            topics = CURRICULUM.get(grade, {}).get(subject.name, [])
            if not topics:
                continue
            for chapter, topic in enumerate(topics, start=1):
                upsert_lesson(
                    subject.id, grade, chapter,
                    f"{subject.name} lớp {grade} - Chương {chapter}: {topic}",
                    build_lesson_content(subject.name, grade, chapter, topic),
                )
                upsert_exercise(
                    subject.id, grade, chapter,
                    f"Bài tập {subject.name} lớp {grade} - Chương {chapter}: {topic}",
                    build_exercise_content(subject.name, grade, chapter, topic),
                    build_answer_key(subject.name, topic),
                )
                upsert_test(
                    subject.id, grade, chapter,
                    f"Kiểm tra chương {chapter} - {subject.name} lớp {grade}",
                    "Trả lời các câu hỏi theo yêu cầu. Đọc kĩ đề trước khi chọn đáp án.",
                    "Tự động chấm bằng đáp án trong ngân hàng câu hỏi.",
                    [],
                )
            Test.query.filter_by(subject_id=subject.id, grade_level=grade, test_type="term").delete()
            midpoint = max(1, len(topics) // 2)
            quarter = max(1, len(topics) // 4)
            hk1_topics = topics[:midpoint]
            hk2_topics = topics[midpoint:] or topics[-midpoint:]
            mid_hk1_topics = hk1_topics[:max(1, min(len(hk1_topics), quarter + 1))]
            mid_hk2_topics = hk2_topics[:max(1, min(len(hk2_topics), quarter + 1))]
            upsert_term_test(subject.id, grade, "midterm_hk1", "Kiểm tra giữa học kì 1", subject.name, mid_hk1_topics)
            upsert_term_test(subject.id, grade, "final_hk1", "Kiểm tra cuối học kì 1", subject.name, hk1_topics)
            upsert_term_test(subject.id, grade, "midterm_hk2", "Kiểm tra giữa học kì 2", subject.name, mid_hk2_topics)
            upsert_term_test(subject.id, grade, "final_hk2", "Kiểm tra cuối học kì 2", subject.name, hk2_topics)

    db.session.commit()
