> Source: [Сетевая_модель_OSI](https://ru.wikipedia.org/w/index.php?title=%D0%A1%D0%B5%D1%82%D0%B5%D0%B2%D0%B0%D1%8F_%D0%BC%D0%BE%D0%B4%D0%B5%D0%BB%D1%8C_OSI&oldid=155501372); author: Wikipedia contributors (see revision history); license: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
> Preparation: Converted article HTML to Markdown; removed references, navigation and footnotes.

**Сетевая модель OSI** (The **Open Systems Interconnection** model) — [сетевая](https://ru.wikipedia.org/wiki/Компьютерная_сеть "Компьютерная сеть") модель стека (магазина) сетевых протоколов OSI/ISO. Посредством данной модели различные сетевые устройства могут взаимодействовать друг с другом. Модель определяет различные уровни взаимодействия систем. Каждый уровень выполняет определённые функции при таком взаимодействии.

Модель OSI была разработана в конце 1970-х годов для поддержания разнообразных методов компьютерных сетей, которые в это время конкурировали за применение в крупных национальных сетевых взаимодействиях во Франции, Великобритании и США. В 1980-х годах она стала рабочим продуктом группы взаимодействия открытых систем [Международной организации по стандартизации](https://ru.wikipedia.org/wiki/Международная_организация_по_стандартизации "Международная организация по стандартизации") (ISO). Модель не смогла дать полное описание сети и не получила поддержку архитекторов на заре Интернета, который впоследствии нашёл отражение в менее предписывающем [TCP/IP](https://ru.wikipedia.org/wiki/TCP/IP "TCP/IP"), в основном под руководством [Инженерного совета Интернета](https://ru.wikipedia.org/wiki/Инженерный_совет_Интернета "Инженерный совет Интернета") (IETF).

[![](https://thumb.wikimedia.org/wikipedia/commons/thumb/8/8d/OSI_Model_v1.svg/langru-250px-OSI_Model_v1.svg.png?utm_source=ru.wikipedia.org&utm_campaign=parser&utm_content=thumbnail)](https://ru.wikipedia.org/wiki/Файл:OSI_Model_v1.svg)

Диаграмма уровней сетевой модели OSI

## История

В начале и середине 1970-х годов сеть в основном либо спонсировалась государством ([NPL network](https://ru.wikipedia.org/wiki/NPL-сеть "NPL-сеть") в Великобритании, [ARPANET](https://ru.wikipedia.org/wiki/ARPANET "ARPANET") в США, CYCLADES во Франции), либо разрабатывалась вендорами с использованием собственных стандартов, таких как IBM Systems Network Architecture и Digital Equipment Corporation DECnet. Общественные сети передачи данных только начинали появляться, и в конце 1970-х годов они использовали стандарт [X.25](https://ru.wikipedia.org/wiki/X.25 "X.25").

[Экспериментальная система коммутации пакетов](https://ru.wikipedia.org/wiki/Коммутация_пакетов#EPSS "Коммутация пакетов") в Великобритании примерно в 1973—1975 годах выявила необходимость определения протоколов более высокого уровня. После публикации британского [Национального вычислительного центра](https://ru.wikipedia.org/wiki/Национальный_вычислительный_центр?action=edit&redlink=1 "Национальный вычислительный центр")^([\[англ.\]](https://en.wikipedia.org/wiki/National%20Computing%20Centre "en:National Computing Centre")) «Для чего нужны распределённые вычисления», ставшей результатом крупных исследований будущих конфигураций компьютерных систем, Великобритания представила аргументы в пользу создания Международной комиссии по стандартам для охвата этой области на совещании ISO в Сиднее в марте 1977 года.

С 1977 года ISO реализовала программу по разработке общих стандартов и методов сетевого взаимодействия. Аналогичный процесс развивался и в [Международном консультативном комитете по телеграфии и телефонии](https://ru.wikipedia.org/wiki/Международный_консультативный_комитет_по_телеграфии_и_телефонии "Международный консультативный комитет по телеграфии и телефонии") (МККТТ). Оба органа разработали документы, определяющие схожие сетевые модели. Модель OSI была впервые определена в исходном виде в [Вашингтоне](https://ru.wikipedia.org/wiki/Вашингтон "Вашингтон") в феврале 1978 года французом [Хьюбертом Циммерманом](https://ru.wikipedia.org/wiki/Циммерман,_Хьюберт?action=edit&redlink=1 "Циммерман, Хьюберт")^([\[англ.\]](https://en.wikipedia.org/wiki/Hubert%20Zimmermann "en:Hubert Zimmermann")), немного доработанный проект стандарта был опубликован ISO в 1980 году.

Разработчикам модели пришлось столкнуться с конкурирующими приоритетами и интересами. Темпы технологических изменений обусловили необходимость определения стандартов, к которым новые системы могли бы сходиться, а не стандартизировать процедуры постфактум, тогда как традиционный подход к разработке стандартов был противоположным. Хотя это и не был сам стандарт, он представлял собой основу, на базе которой можно было бы определить будущие стандарты.

В 1983 году документы МККТТ и ISO были объединены и таким образом была сформирована базовая эталонная модель взаимосвязи открытых систем, обычно и называемая эталонной моделью взаимосвязи открытых систем ([англ.](https://ru.wikipedia.org/wiki/Английский_язык "Английский язык") [Open Systems Interconnection](https://ru.wikipedia.org/wiki/Open_Systems_Interconnection "Open Systems Interconnection"), OSI) или просто моделью OSI. Объединённый документ был опубликован в 1984 году (ISO — как стандарт ISO 7498, МККТТ — как Рекомендация МККТТ X.200 (ныне — Рекомендация МСЭ-Т X.200, поскольку в 1993 году МККТТ был преобразован в Сектор стандартизации электросвязи [Международного союза электросвязи](https://ru.wikipedia.org/wiki/Международный_союз_электросвязи "Международный союз электросвязи") (МСЭ-Т))).

OSI состояла из двух основных компонентов: абстрактной модели сети, называемой базовой эталонной моделью или семислойной моделью, и набора сетевых протоколов. Основываясь на идее согласованной модели уровней протоколов, определяющей взаимодействие между сетевыми устройствами и программным обеспечением, эталонная модель OSI стала крупным достижением в стандартизации концепций сетевого взаимодействия.

Концепция семислойной модели была описана в работе американца [Чарльза Бахмана](https://ru.wikipedia.org/wiki/Бахман,_Чарльз_Уильям "Бахман, Чарльз Уильям") из компании [Honeywell Information Systems](https://ru.wikipedia.org/wiki/Honeywell "Honeywell"). Различные аспекты структуры OSI эволюционировали из опыта работы с сетью NPL, ARPANET, CYCLADES, EIN и [International Networking Working Group](https://ru.wikipedia.org/wiki/International_Networking_Working_Group?action=edit&redlink=1 "International Networking Working Group")^([\[англ.\]](https://en.wikipedia.org/wiki/International%20Networking%20Working%20Group "en:International Networking Working Group")) ([IFIP](https://ru.wikipedia.org/wiki/Международная_федерация_по_обработке_информации "Международная федерация по обработке информации") WG6.1). В этой модели система сетевого взаимодействия была разделена на слои. Внутри каждого слоя один или несколько объектов реализовывали его функциональность. Каждая сущность взаимодействовала непосредственно только со слоем, находящимся прямо под ней, и предоставляла средства для использования слоем, находящимся над ней.

OSI таким образом стала попыткой участников отрасли согласовать общие сетевые стандарты для обеспечения совместимости с оборудованием разных производителей. Для больших сетей зачастую поддерживались несколько наборов сетевых протоколов, причём многие устройства не могли взаимодействовать с другими устройствами именно из-за отсутствия общих протоколов.

В конце 1980-х и начале 1990-х годов в плане построения максимально надёжных компьютерных сетей с моделью OSI стал активно [конкурировать](https://en.wikipedia.org/wiki/Protocol%20Wars "en:Protocol Wars") [Набор интернет-протоколов](https://ru.wikipedia.org/wiki/TCP/IP "TCP/IP") (TCP/IP), который стал широко использоваться в сетях с оборудованием разных производителей для работы в интернете. Тем не менее, модель OSI до сих пор используется в качестве эталона для обучения и документации.

## Концепция

### Стандарты

Модель OSI, которая была определена в серии стандартов ISO/IEC 7498, состоит из следующих частей:

- ISO/IEC 7498-1 — базовая модель;
- ISO/IEC 7498-2 — архитектура безопасности;
- ISO/IEC 7498-3 — наименования и адресация;
- ISO/IEC 7498-4 — система менеджмента.

ISO/IEC 7498-1 также опубликован в качестве Рекомендации МСЭ-Т X.200. Некоторые спецификации протокола также были доступны в рамках других Рекомендаций МСЭ-Т серии X. Эквивалентные стандарты ISO и ISO/IEC для модели OSI были доступны в ISO. Не все из них бесплатны.

### Основные принципы

Протоколы связи позволяют структуре на одном хосте взаимодействовать с соответствующей структурой того же уровня на другом хосте.

На каждом уровне N два объекта обмениваются блоками данных ([PDU](https://ru.wikipedia.org/wiki/Блок_данных_протокола "Блок данных протокола")) с помощью протокола данного уровня на соответствующих устройствах. Каждый PDU содержит блок служебных данных ([SDU](https://en.wikipedia.org/wiki/Service%20data%20unit "en:Service data unit")), связанный с верхним или нижним протоколом.

Обработка данных двумя взаимодействующими OSI-совместимыми устройствами происходит следующим образом:

1.  Передаваемые данные составляются на самом верхнем уровне передающего устройства (уровень N) в протокольный блок данных (PDU).
2.  PDU передаётся на уровень N-1, где он становится сервисным блоком данных (SDU).
3.  На уровне N-1 SDU объединяется с верхним, нижним или обоими уровнями, создавая слой N-1 PDU. Затем он передаётся в слой N-2.
4.  Процесс продолжается до достижения самого нижнего уровня, с которого данные передаются на принимающее устройство.
5.  На приёмном устройстве данные передаются от самого низкого уровня к самому высокому в виде серии SDU, последовательно удаляясь из верхнего или нижнего колонтитула каждого слоя до достижения самого верхнего уровня, где принимаются последние данные.

### Уровни модели OSI

[TABLE]

В литературе наиболее часто принято начинать описание уровней модели OSI с седьмого уровня, называемого прикладным, на котором пользовательские приложения обращаются к сети. Модель OSI заканчивается 1-м уровнем — физическим, на котором определены стандарты, предъявляемые независимыми производителями к средам передачи данных:

- тип передающей среды (медный кабель, оптоволокно, радиоэфир и др.);
- тип модуляции сигнала;
- сигнальные уровни логических дискретных состояний (нули и единицы).

Любой протокол модели OSI должен взаимодействовать либо с протоколами своего уровня, либо с протоколами на единицу выше и/или ниже своего уровня. Взаимодействия с протоколами своего уровня называются горизонтальными, а с уровнями на единицу выше или ниже — вертикальными. Любой протокол модели OSI может выполнять только функции своего уровня и не может выполнять функций другого уровня, что не выполняется в протоколах альтернативных моделей.

Каждому уровню с некоторой долей условности соответствует свой операнд — логически неделимый элемент данных, которым на отдельном уровне можно оперировать в рамках модели и используемых протоколов: на физическом уровне мельчайшая единица — бит, на канальном уровне информация объединена в кадры, на сетевом — в пакеты (датаграммы), на транспортном — в сегменты. Любой фрагмент данных, логически объединённых для передачи — кадр, пакет, датаграмма — считается сообщением. Именно сообщения в общем виде являются операндами сеансового, представления и прикладного уровней.

К базовым сетевым технологиям относятся физический и канальный уровни.

#### Прикладной уровень

Основная статья: [Прикладной уровень](https://ru.wikipedia.org/wiki/Прикладной_уровень "Прикладной уровень")

Прикладной уровень (уровень приложений; [англ.](https://ru.wikipedia.org/wiki/Английский_язык "Английский язык") application layer) — верхний уровень модели, обеспечивающий взаимодействие пользовательских приложений с сетью:

- позволяет приложениям использовать сетевые службы:
  - удалённый доступ к файлам и базам данных;
  - пересылка электронной почты;
- отвечает за передачу служебной информации;
- предоставляет приложениям информацию об ошибках;
- формирует запросы к уровню представления.

Протоколы прикладного уровня: [RDP](https://ru.wikipedia.org/wiki/Remote_Desktop_Protocol "Remote Desktop Protocol"), [HTTP](https://ru.wikipedia.org/wiki/HTTP "HTTP"), [SMTP](https://ru.wikipedia.org/wiki/SMTP "SMTP"), [SNMP](https://ru.wikipedia.org/wiki/SNMP "SNMP"), [POP3](https://ru.wikipedia.org/wiki/Post_Office_Protocol "Post Office Protocol"), [FTP](https://ru.wikipedia.org/wiki/FTP "FTP"), [XMPP](https://ru.wikipedia.org/wiki/XMPP "XMPP"), [OSCAR](https://ru.wikipedia.org/wiki/OSCAR "OSCAR"), [Modbus](https://ru.wikipedia.org/wiki/Modbus "Modbus"), [SIP](https://ru.wikipedia.org/wiki/SIP "SIP"), [TELNET](https://ru.wikipedia.org/wiki/TELNET "TELNET") и другие.

Определения протокола прикладного уровня и уровня представления очень размыты, и принадлежность протокола к тому или иному уровню, например, протокола HTTPS, зависит от конечного сервиса который предоставляет приложение.

В том случае, если протокол, например, HTTPS, используется для просмотра некой простой интернет-страницы через браузер, его можно рассматривать как протокол прикладного уровня. В том же случае, если протокол HTTPS используется как низкоуровневый протокол для передачи финансовой информации, например, по протоколу ISO 8583, то протокол HTTPS будет являться протоколом уровня представления, а протокол ISO 8583 — протоколом уровня приложения. То же касается иных протоколов прикладного уровня^(\[*[источник не указан 2004 дня](https://ru.wikipedia.org/wiki/Википедия:Ссылки_на_источники "Википедия:Ссылки на источники")*\]).

#### Уровень представления

Основная статья: [Уровень представления](https://ru.wikipedia.org/wiki/Уровень_представления "Уровень представления")

Уровень представления ([англ.](https://ru.wikipedia.org/wiki/Английский_язык "Английский язык") presentation layer) обеспечивает преобразование протоколов и кодирование/декодирование данных. Запросы приложений, полученные с прикладного уровня, на уровне представления преобразуются в формат для передачи по сети, а полученные из сети данные преобразуются в формат приложений. На этом уровне может осуществляться сжатие/распаковка или шифрование/дешифрование, а также перенаправление запросов другому сетевому ресурсу, если они не могут быть обработаны локально.

Уровень представлений обычно представляет собой промежуточный протокол для преобразования информации из соседних уровней. Это позволяет осуществлять обмен между приложениями на разнородных компьютерных системах прозрачным для приложений образом. Уровень представлений обеспечивает форматирование и преобразование кода. Форматирование кода используется для того, чтобы гарантировать приложению поступление информации для обработки, которая имела бы для него смысл. При необходимости этот уровень может выполнять перевод из одного формата данных в другой.

Уровень представлений имеет дело не только с форматами и представлением данных, он также занимается структурами данных, которые используются программами. Таким образом, уровень 6 обеспечивает организацию данных при их пересылке.

Чтобы понять, как это работает, представим, что имеются две системы. Одна использует для представления данных расширенный двоичный код обмена информацией [EBCDIC](https://ru.wikipedia.org/wiki/EBCDIC "EBCDIC"), например, это может быть [мейнфрейм](https://ru.wikipedia.org/wiki/Мейнфрейм "Мейнфрейм") компании [IBM](https://ru.wikipedia.org/wiki/IBM "IBM"), а другая — американский стандартный код обмена информацией [ASCII](https://ru.wikipedia.org/wiki/ASCII "ASCII") (его использует большинство других производителей компьютеров). Если этим двум системам необходимо обменяться информацией, то нужен уровень представлений, который выполнит преобразование и осуществит перевод между двумя различными форматами.

Другой функцией, выполняемой на уровне представлений, является шифрование данных, которое применяется в тех случаях, когда необходимо защитить передаваемую информацию от доступа несанкционированными получателями. Чтобы решить эту задачу, процессы и коды, находящиеся на уровне представлений, должны выполнить преобразование данных. На этом уровне существуют и другие подпрограммы, которые сжимают тексты и преобразовывают графические изображения в битовые потоки, так, что они могут передаваться по сети.

Стандарты уровня представлений также определяют способы представления графических изображений. Для этих целей может использоваться формат [PICT](https://ru.wikipedia.org/wiki/PICT?action=edit&redlink=1 "PICT") — формат изображений, применяемый для передачи графики QuickDraw между программами.

Другим форматом представлений является тэгированный формат файлов изображений [TIFF](https://ru.wikipedia.org/wiki/TIFF "TIFF"), который обычно используется для растровых изображений с высоким [разрешением](https://ru.wikipedia.org/wiki/Разрешение_(компьютерная_графика) "Разрешение (компьютерная графика)"). Следующим стандартом уровня представлений, который может использоваться для графических изображений, является стандарт, разработанный Объединённой экспертной группой по фотографии (Joint Photographic Expert Group); в повседневном пользовании этот стандарт называют просто [JPEG](https://ru.wikipedia.org/wiki/JPEG "JPEG").

Существует другая группа стандартов уровня представлений, которая определяет представление звука и кинофрагментов. Сюда входят интерфейс электронных музыкальных инструментов ([англ.](https://ru.wikipedia.org/wiki/Английский_язык "Английский язык") Musical Instrument Digital Interface, [MIDI](https://ru.wikipedia.org/wiki/MIDI "MIDI")) для цифрового представления музыки, разработанный Экспертной группой по кинематографии стандарт [MPEG](https://ru.wikipedia.org/wiki/MPEG "MPEG"), используемый для сжатия и кодирования видеороликов на компакт-дисках, хранения в оцифрованном виде и передачи со скоростями до 1,5 Мбит/с, и [QuickTime](https://ru.wikipedia.org/wiki/QuickTime "QuickTime") — стандарт, описывающий звуковые и видео элементы для программ, выполняемых на компьютерах Macintosh и PowerPC.

Протоколы уровня представления: AFP — [Apple Filing Protocol](https://ru.wikipedia.org/wiki/Apple_Filing_Protocol "Apple Filing Protocol"), ICA — [Independent Computing Architecture](https://ru.wikipedia.org/wiki/Independent_Computing_Architecture "Independent Computing Architecture"), LPP — Lightweight Presentation Protocol, NCP — [NetWare Core Protocol](https://ru.wikipedia.org/wiki/NetWare_Core_Protocol "NetWare Core Protocol"), NDR — [Network Data Representation](https://ru.wikipedia.org/wiki/Network_Data_Representation?action=edit&redlink=1 "Network Data Representation"), XDR — [eXternal Data Representation](https://ru.wikipedia.org/wiki/External_Data_Representation "External Data Representation"), X.25 PAD — [Packet Assembler/Disassembler Protocol](https://ru.wikipedia.org/wiki/X.25 "X.25").

#### Сеансовый уровень

Основная статья: [Сеансовый уровень](https://ru.wikipedia.org/wiki/Сеансовый_уровень "Сеансовый уровень")

Сеансовый уровень ([англ.](https://ru.wikipedia.org/wiki/Английский_язык "Английский язык") session layer) модели обеспечивает поддержание сеанса связи, позволяя приложениям взаимодействовать между собой длительное время. Уровень управляет созданием/завершением сеанса, обменом информацией, синхронизацией задач, определением права на передачу данных и поддержанием сеанса в периоды неактивности приложений.

Протоколы сеансового уровня: H.245 ([Call Control Protocol for Multimedia Communication](https://ru.wikipedia.org/wiki/H.245 "H.245")), ISO-SP (OSI Session Layer Protocol (X.225, ISO 8327)), iSNS ([Internet Storage Name Service](https://ru.wikipedia.org/wiki/Internet_Storage_Name_Service "Internet Storage Name Service")), L2F ([Layer 2 Forwarding Protocol](https://ru.wikipedia.org/wiki/Layer_2_Forwarding_Protocol "Layer 2 Forwarding Protocol")), L2TP ([Layer 2 Tunneling Protocol](https://ru.wikipedia.org/wiki/L2TP "L2TP")), NetBIOS ([Network Basic Input Output System](https://ru.wikipedia.org/wiki/NetBIOS "NetBIOS")), PAP ([Password Authentication Protocol](https://ru.wikipedia.org/wiki/Password_Authentication_Protocol "Password Authentication Protocol")), PPTP ([Point-to-Point Tunneling Protocol](https://ru.wikipedia.org/wiki/PPTP "PPTP")), RPC ([Remote Procedure Call Protocol](https://ru.wikipedia.org/wiki/Remote_procedure_call "Remote procedure call")), RTCP ([Real-time Transport Control Protocol](https://ru.wikipedia.org/wiki/RTCP "RTCP")), SMPP ([Short Message Peer-to-Peer](https://ru.wikipedia.org/wiki/SMPP "SMPP")), SCP ([Session Control Protocol](https://ru.wikipedia.org/wiki/Session_Control_Protocol?action=edit&redlink=1 "Session Control Protocol")), ZIP ([Zone Information Protocol](https://ru.wikipedia.org/wiki/Zone_Information_Protocol "Zone Information Protocol")), SDP ([Sockets Direct Protocol](https://ru.wikipedia.org/wiki/Sockets_Direct_Protocol "Sockets Direct Protocol"))…

#### Транспортный уровень

Основная статья: [Транспортный уровень](https://ru.wikipedia.org/wiki/Транспортный_уровень "Транспортный уровень")

Транспортный уровень ([англ.](https://ru.wikipedia.org/wiki/Английский_язык "Английский язык") transport layer) модели предназначен для обеспечения надёжной передачи данных от отправителя к получателю. При этом уровень надёжности может варьировать в широких пределах. Существует множество классов протоколов транспортного уровня, начиная от протоколов, предоставляющих только основные транспортные функции (например, функции передачи данных без подтверждения приёма), и заканчивая протоколами, которые гарантируют доставку в пункт назначения нескольких пакетов данных в надлежащей последовательности, мультиплексируют несколько потоков данных, обеспечивают механизм управления потоками данных и гарантируют достоверность принятых данных. Например, [UDP](https://ru.wikipedia.org/wiki/UDP "UDP") ограничивается контролем целостности данных в рамках одной датаграммы и не исключает возможности потери пакета целиком или дублирования пакетов, нарушение порядка получения пакетов данных; [TCP](https://ru.wikipedia.org/wiki/TCP "TCP") обеспечивает надёжную непрерывную передачу данных, исключающую потерю данных или нарушение порядка их поступления или дублирования, может перераспределять данные, разбивая большие порции данных на фрагменты и наоборот, склеивая фрагменты в один пакет.

Протоколы транспортного уровня: ATP ([AppleTalk Transaction Protocol](https://ru.wikipedia.org/wiki/AppleTalk "AppleTalk")), CUDP ([Cyclic UDP](https://ru.wikipedia.org/wiki/Cyclic_UDP?action=edit&redlink=1 "Cyclic UDP")), DCCP ([Datagram Congestion Control Protocol](https://ru.wikipedia.org/wiki/Datagram_Congestion_Control_Protocol "Datagram Congestion Control Protocol")), FCP ([Fibre Channel Protocol](https://ru.wikipedia.org/wiki/Fibre_Channel "Fibre Channel")), IL ([IL Protocol](https://ru.wikipedia.org/wiki/IL_Protocol "IL Protocol")), NBF ([NetBIOS Frames protocol](https://ru.wikipedia.org/wiki/NetBIOS_Frame_Protocol "NetBIOS Frame Protocol")), NCP ([NetWare Core Protocol](https://ru.wikipedia.org/wiki/NetWare_Core_Protocol "NetWare Core Protocol")), SCTP ([Stream Control Transmission Protocol](https://ru.wikipedia.org/wiki/Stream_Control_Transmission_Protocol "Stream Control Transmission Protocol")), SPX ([Sequenced Packet Exchange](https://ru.wikipedia.org/wiki/IPX/SPX "IPX/SPX")), SST ([Structured Stream Transport](https://ru.wikipedia.org/wiki/Structured_Stream_Transport "Structured Stream Transport")), TCP ([Transmission Control Protocol](https://ru.wikipedia.org/wiki/Transmission_Control_Protocol "Transmission Control Protocol")), UDP ([User Datagram Protocol](https://ru.wikipedia.org/wiki/User_Datagram_Protocol "User Datagram Protocol")).

#### Сетевой уровень

Основная статья: [Сетевой уровень](https://ru.wikipedia.org/wiki/Сетевой_уровень "Сетевой уровень")

Сетевой уровень ([англ.](https://ru.wikipedia.org/wiki/Английский_язык "Английский язык") network layer) модели предназначен для определения пути передачи данных. Отвечает за трансляцию логических адресов и имён в физические, определение кратчайших маршрутов, отслеживание неполадок и «заторов» в сети.

Протоколы сетевого уровня маршрутизируют данные от источника к получателю. Работающие на этом уровне устройства ([маршрутизаторы](https://ru.wikipedia.org/wiki/Маршрутизатор "Маршрутизатор")) условно называют устройствами третьего уровня (по номеру уровня в модели OSI).

Протоколы сетевого уровня: IP/IPv4/IPv6 ([Internet Protocol](https://ru.wikipedia.org/wiki/Internet_Protocol "Internet Protocol")), IPX ([Internetwork Packet Exchange](https://ru.wikipedia.org/wiki/Internetwork_Packet_Exchange "Internetwork Packet Exchange"), протокол межсетевого обмена), X.25 (частично этот протокол реализован на уровне 2), CLNP (сетевой протокол без организации соединений), IPsec ([Internet Protocol Security](https://ru.wikipedia.org/wiki/Internet_Protocol_Security "Internet Protocol Security")).

Протоколы маршрутизации — RIP ([Routing Information Protocol](https://ru.wikipedia.org/wiki/Routing_Information_Protocol "Routing Information Protocol")), OSPF ([Open Shortest Path First](https://ru.wikipedia.org/wiki/Open_Shortest_Path_First "Open Shortest Path First")).

#### Канальный уровень

Основная статья: [Канальный уровень](https://ru.wikipedia.org/wiki/Канальный_уровень "Канальный уровень")

Канальный уровень ([англ.](https://ru.wikipedia.org/wiki/Английский_язык "Английский язык") data link layer) предназначен для обеспечения взаимодействия сетей на физическом уровне и контроля ошибок, которые могут возникнуть. Полученные с физического уровня данные, представленные в битах, он упаковывает в [кадры](https://ru.wikipedia.org/wiki/Кадр_(телекоммуникации) "Кадр (телекоммуникации)"), проверяет их на целостность и, если нужно, исправляет ошибки (либо формирует повторный запрос повреждённого кадра) и отправляет на сетевой уровень. Канальный уровень может взаимодействовать с одним или несколькими физическими уровнями, контролируя и управляя этим взаимодействием.

Спецификация [IEEE 802](https://ru.wikipedia.org/wiki/IEEE_802 "IEEE 802") разделяет этот уровень на два подуровня: [MAC](https://ru.wikipedia.org/wiki/Media_Access_Control "Media Access Control") ([англ.](https://ru.wikipedia.org/wiki/Английский_язык "Английский язык") media access control) регулирует доступ к разделяемой физической среде, [LLC](https://ru.wikipedia.org/wiki/Logical_link_control "Logical link control") ([англ.](https://ru.wikipedia.org/wiki/Английский_язык "Английский язык") logical link control) обеспечивает обслуживание сетевого уровня.

На этом уровне работают [коммутаторы](https://ru.wikipedia.org/wiki/Сетевой_коммутатор "Сетевой коммутатор"), [мосты](https://ru.wikipedia.org/wiki/Сетевой_мост "Сетевой мост") и другие устройства. Эти устройства используют адресацию второго уровня (по номеру уровня в модели OSI).

Протоколы канального уровня: [ARCnet](https://ru.wikipedia.org/wiki/ARCnet "ARCnet"), [ATM](https://ru.wikipedia.org/wiki/Asynchronous_Transfer_Mode "Asynchronous Transfer Mode"), [Controller Area Network](https://ru.wikipedia.org/wiki/Controller_Area_Network "Controller Area Network") (CAN), [Econet](https://ru.wikipedia.org/wiki/Econet "Econet"), [IEEE 802.3](https://ru.wikipedia.org/wiki/IEEE_802.3 "IEEE 802.3") ([Ethernet](https://ru.wikipedia.org/wiki/Ethernet "Ethernet")), [Ethernet Automatic Protection Switching](https://ru.wikipedia.org/wiki/Ethernet_Automatic_Protection_Switching "Ethernet Automatic Protection Switching") (EAPS), [Fiber Distributed Data Interface](https://ru.wikipedia.org/wiki/Fiber_Distributed_Data_Interface "Fiber Distributed Data Interface") (FDDI), [Frame Relay](https://ru.wikipedia.org/wiki/Frame_Relay "Frame Relay"), [High-Level Data Link Control](https://ru.wikipedia.org/wiki/High-Level_Data_Link_Control "High-Level Data Link Control") (HDLC), [IEEE 802.2](https://ru.wikipedia.org/wiki/IEEE_802.2 "IEEE 802.2") (предоставляет функции LLC для подуровня IEEE 802 MAC), [Link Access Procedures, D channel](https://ru.wikipedia.org/wiki/Link_Access_Procedures,_D_channel?action=edit&redlink=1 "Link Access Procedures, D channel") (LAPD), [IEEE 802.11](https://ru.wikipedia.org/wiki/IEEE_802.11 "IEEE 802.11") [wireless LAN](https://ru.wikipedia.org/wiki/Wireless_LAN "Wireless LAN"), [LocalTalk](https://ru.wikipedia.org/wiki/LocalTalk "LocalTalk"), [Multiprotocol Label Switching](https://ru.wikipedia.org/wiki/Multiprotocol_Label_Switching "Multiprotocol Label Switching") (MPLS), [Point-to-Point Protocol](https://ru.wikipedia.org/wiki/Point-to-Point_Protocol "Point-to-Point Protocol") (PPP), [Point-to-Point Protocol over Ethernet](https://ru.wikipedia.org/wiki/PPPoE "PPPoE") (PPPoE), [Serial Line Internet Protocol](https://ru.wikipedia.org/wiki/SLIP "SLIP") (SLIP, устарел), [StarLan](https://ru.wikipedia.org/wiki/StarLan "StarLan"), [Token ring](https://ru.wikipedia.org/wiki/Token_ring "Token ring"), [Unidirectional Link Detection](https://ru.wikipedia.org/wiki/Unidirectional_Link_Detection?action=edit&redlink=1 "Unidirectional Link Detection")^([\[англ.\]](https://en.wikipedia.org/wiki/Unidirectional%20Link%20Detection "en:Unidirectional Link Detection")) (UDLD), [X.25](https://ru.wikipedia.org/wiki/X.25 "X.25"), [ARP](https://ru.wikipedia.org/wiki/ARP "ARP").

При разработке стеков протоколов на этом уровне решаются задачи помехоустойчивого кодирования. К таким способам кодирования относится [код Хемминга](https://ru.wikipedia.org/wiki/Код_Хэмминга "Код Хэмминга"), блочное кодирование, [код Рида — Соломона](https://ru.wikipedia.org/wiki/Код_Рида_—_Соломона "Код Рида — Соломона").

В программировании этот уровень представляет [драйвер](https://ru.wikipedia.org/wiki/Драйвер "Драйвер") сетевой платы, в [операционных системах](https://ru.wikipedia.org/wiki/Операционная_система "Операционная система") имеется программный интерфейс взаимодействия канального и сетевого уровней между собой. Это не новый уровень, а просто реализация модели для конкретной ОС. Примеры таких интерфейсов: [ODI](https://ru.wikipedia.org/wiki/ODI_(интерфейс)?action=edit&redlink=1 "ODI (интерфейс)")^([\[англ.\]](https://en.wikipedia.org/wiki/Open%20Data-Link%20Interface "en:Open Data-Link Interface")), [NDIS](https://ru.wikipedia.org/wiki/NDIS "NDIS"), [UDI](https://ru.wikipedia.org/wiki/UDI?action=edit&redlink=1 "UDI").

#### Физический уровень

Основная статья: [Физический уровень](https://ru.wikipedia.org/wiki/Физический_уровень "Физический уровень")

Физический уровень ([англ.](https://ru.wikipedia.org/wiki/Английский_язык "Английский язык") physical layer) — нижний уровень модели, который определяет метод передачи данных, представленных в двоичном виде, от одного устройства (компьютера) к другому. Составлением таких методов занимаются разные организации, в том числе: [Институт инженеров по электротехнике и электронике](https://ru.wikipedia.org/wiki/Институт_инженеров_электротехники_и_электроники "Институт инженеров электротехники и электроники"), [Альянс электронной промышленности](https://ru.wikipedia.org/wiki/Electronic_Industries_Alliance "Electronic Industries Alliance"), [Европейский институт телекоммуникационных стандартов](https://ru.wikipedia.org/wiki/Европейский_институт_телекоммуникационных_стандартов "Европейский институт телекоммуникационных стандартов") и другие. Осуществляют передачу электрических или оптических сигналов в кабель или в радиоэфир и, соответственно, их приём и преобразование в биты данных в соответствии с [методами кодирования цифровых сигналов](https://ru.wikipedia.org/wiki/Физическое_кодирование "Физическое кодирование").

На этом уровне также работают [концентраторы](https://ru.wikipedia.org/wiki/Сетевой_концентратор "Сетевой концентратор"), [повторители](https://ru.wikipedia.org/wiki/Повторитель_(сетевое_оборудование) "Повторитель (сетевое оборудование)") сигнала и [медиаконвертеры](https://ru.wikipedia.org/wiki/Медиаконвертер "Медиаконвертер").

Функции физического уровня реализуются на всех устройствах, подключённых к сети. Со стороны компьютера функции физического уровня выполняются сетевым адаптером или последовательным портом. К физическому уровню относятся физические, электрические и механические интерфейсы между двумя системами. Физический уровень определяет такие виды сред передачи данных как [оптоволокно](https://ru.wikipedia.org/wiki/Оптическое_волокно "Оптическое волокно"), [витая пара](https://ru.wikipedia.org/wiki/Витая_пара "Витая пара"), [коаксиальный кабель](https://ru.wikipedia.org/wiki/Коаксиальный_кабель "Коаксиальный кабель"), спутниковый канал передач данных и т. п. Стандартными типами сетевых интерфейсов, относящимися к физическому уровню, являются: [V.35](https://ru.wikipedia.org/wiki/V.35 "V.35"), [RS-232](https://ru.wikipedia.org/wiki/RS-232 "RS-232"), [RS-485](https://ru.wikipedia.org/wiki/RS-485 "RS-485"), [RJ-11](https://ru.wikipedia.org/wiki/RJ-45 "RJ-45"), [RJ-45](https://ru.wikipedia.org/wiki/RJ-45 "RJ-45"), разъёмы [AUI](https://ru.wikipedia.org/wiki/AUI "AUI") и [BNC](https://ru.wikipedia.org/wiki/BNC-коннектор "BNC-коннектор").

При разработке стеков протоколов на этом уровне решаются задачи синхронизации и линейного кодирования. К таким способам кодирования относится [код NRZ](https://ru.wikipedia.org/wiki/NRZ_(прямой) "NRZ (прямой)"), [код RZ](https://ru.wikipedia.org/wiki/RZ "RZ"), [MLT-3](https://ru.wikipedia.org/wiki/MLT-3 "MLT-3"), [PAM5](https://ru.wikipedia.org/wiki/Потенциальный_код_2B1Q "Потенциальный код 2B1Q"), [Манчестер II](https://ru.wikipedia.org/wiki/Манчестерский_код "Манчестерский код").

Протоколы физического уровня: [IEEE 802.15 (Bluetooth)](https://ru.wikipedia.org/wiki/Bluetooth "Bluetooth"), [IRDA](https://ru.wikipedia.org/wiki/Infrared_Data_Association "Infrared Data Association"), [EIA](https://ru.wikipedia.org/wiki/Electronic_Industries_Alliance "Electronic Industries Alliance") [RS-232](https://ru.wikipedia.org/wiki/RS-232 "RS-232"), [EIA-422](https://ru.wikipedia.org/wiki/EIA-422 "EIA-422"), [EIA-423](https://ru.wikipedia.org/wiki/RS-423 "RS-423"), [RS-449](https://ru.wikipedia.org/wiki/RS-449 "RS-449"), [RS-485](https://ru.wikipedia.org/wiki/RS-485 "RS-485"), [DSL](https://ru.wikipedia.org/wiki/Digital_subscriber_line "Digital subscriber line"), [ISDN](https://ru.wikipedia.org/wiki/Integrated_Services_Digital_Network "Integrated Services Digital Network"), [SONET/SDH](https://ru.wikipedia.org/wiki/Synchronous_optical_network "Synchronous optical network"), [802.11](https://ru.wikipedia.org/wiki/802.11 "802.11") [Wi-Fi](https://ru.wikipedia.org/wiki/Wi-Fi "Wi-Fi"), [Etherloop](https://ru.wikipedia.org/wiki/Etherloop "Etherloop"), [GSM](https://ru.wikipedia.org/wiki/GSM "GSM") [Um radio interface](https://ru.wikipedia.org/wiki/Um_Interface?action=edit&redlink=1 "Um Interface"), ряд протоколов [МСЭ-Т](https://ru.wikipedia.org/wiki/Сектор_стандартизации_электросвязи_МСЭ "Сектор стандартизации электросвязи МСЭ") [G.hn](https://ru.wikipedia.org/wiki/G.hn?action=edit&redlink=1 "G.hn")^([\[англ.\]](https://en.wikipedia.org/wiki/G.hn "en:G.hn")), [TransferJet](https://ru.wikipedia.org/wiki/TransferJet?action=edit&redlink=1 "TransferJet")^([\[англ.\]](https://en.wikipedia.org/wiki/TransferJet "en:TransferJet")), [ARINC 818](https://ru.wikipedia.org/wiki/ARINC_818?action=edit&redlink=1 "ARINC 818"), [G.hn](https://ru.wikipedia.org/wiki/G.hn?action=edit&redlink=1 "G.hn")/[G.9960](https://ru.wikipedia.org/wiki/G.9960?action=edit&redlink=1 "G.9960"), [Modbus Plus](https://ru.wikipedia.org/wiki/Modbus_Plus?action=edit&redlink=1 "Modbus Plus").

## Соответствие модели OSI и других моделей сетевого взаимодействия

Поскольку наиболее востребованными и практически используемыми стали протоколы (например TCP/IP), разработанные с использованием других моделей сетевого взаимодействия, далее необходимо описать возможное включение отдельных протоколов других моделей в различные уровни модели OSI.

### Семейство TCP/IP

Семейство [TCP/IP](https://ru.wikipedia.org/wiki/TCP/IP "TCP/IP") имеет три транспортных протокола: TCP, полностью соответствующий OSI, обеспечивающий проверку получения данных; [UDP](https://ru.wikipedia.org/wiki/UDP "UDP"), отвечающий транспортному уровню только наличием порта, обеспечивающий обмен [датаграммами](https://ru.wikipedia.org/wiki/Дейтаграмма "Дейтаграмма") между приложениями, не гарантирующий получения данных; и [SCTP](https://ru.wikipedia.org/wiki/SCTP "SCTP"), разработанный для устранения некоторых недостатков TCP, в который добавлены некоторые новшества. В семействе TCP/IP есть ещё около двухсот протоколов, самым известным из которых является служебный протокол [ICMP](https://ru.wikipedia.org/wiki/ICMP "ICMP"), используемый для внутренних нужд обеспечения работы; остальные также не являются транспортными протоколами.

### Семейство IPX/SPX

В семействе [IPX/SPX](https://ru.wikipedia.org/wiki/IPX/SPX "IPX/SPX") порты появляются в протоколе сетевого уровня IPX, обеспечивая обмен [датаграммами](https://ru.wikipedia.org/wiki/Дейтаграмма "Дейтаграмма") между приложениями (операционная система резервирует часть сокетов для себя). Протокол SPX, в свою очередь, дополняет IPX всеми остальными возможностями транспортного уровня в полном соответствии с OSI.

В качестве адреса хоста ICX использует идентификатор, образованный из четырёхбайтного номера сети (назначаемого [маршрутизаторами](https://ru.wikipedia.org/wiki/Маршрутизатор "Маршрутизатор")) и MAC-адреса сетевого адаптера.

## Критика

В конце 1990-х годов семиуровневая модель OSI критиковалась отдельными авторами. В частности, в книге «UNIX. Руководство системного администратора» Эви Немет ([англ.](https://ru.wikipedia.org/wiki/Английский_язык "Английский язык") Evi Nemeth) писала:

> Пока комитеты [ISO](https://ru.wikipedia.org/wiki/ISO "ISO") спорили о своих стандартах, за их спиной менялась вся концепция организации сетей и по всему миру внедрялся протокол [TCP/IP](https://ru.wikipedia.org/wiki/TCP/IP "TCP/IP").
>
> \<…\>
>
> И вот, когда протоколы ISO были наконец реализованы, выявился целый ряд проблем:
>
> - эти протоколы основывались на концепциях, не имеющих в современных сетях никакого смысла;
> - их спецификации были в некоторых случаях неполными;
> - по своим функциональным возможностям они уступали другим протоколам;
> - наличие многочисленных уровней сделало эти протоколы медлительными и трудными для реализации.
>
> \<…\>
>
> Сейчас даже самые ярые сторонники этих протоколов признают, что OSI постепенно движется к тому, чтобы стать маленькой сноской на страницах истории компьютеров.
>
> — Эви Нэмет

Несмотря на то, что модель OSI до сих пор используется в качестве эталона для обучения и документации, протоколы OSI, изначально задуманные для этой модели, не получили популярности. Некоторые инженеры утверждают, что эталонная модель OSI всё ещё актуальна для облачных вычислений. Другие считают, что оригинальная модель OSI не соответствует современным сетевым протоколам, и вместо этого предлагают упрощённый подход.
