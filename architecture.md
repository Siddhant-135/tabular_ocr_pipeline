## Structured transcription repository

### Structure of the page:
the pages have uniform width w and height h, with h > w. The rows of data are between fixed h values since have scanned keeping a uniform scale and positions of images, but with some fault values. 

### Row extraction mechanism
We can characterise extracting individual rows from the images with a "start_h" value, "row_h" height values (there are total 31 rows in an arithmetic progression with consecutive), and then a margin "margin_factor" say 10, which for every row increases the top and decreases the bottom margin value by row_h/margin_factor. Note that this means individual extrcted rows overlap with each other by design.

### Verification of extraction
Regenerate complete image (original stored in some input/ folder) with the red lines drawn on top of the page and the 31 cropped images available inside a verification/ folder, one folder per input image. this is to make sure something is missed or not.

### VLM Reading
tell me which VLM to install, and then help me install it with uv and venv. We will subsequently run it over each filtered image that we have to extract out each page individually one by one into an output-x.csv in output/ folder. 

#### Center bias
prompt the VLM to recognise the primary text in it's field and only one row of text. there may be sneak in (little bit) from above and below or due to some misplacement. 

#### Parallelise
We can parallelise the vlm processing if required across files. however, i want to use a good vlm to make sure the extraction is proper.

#### Regex Checks
the data follow some very significant structure that we must use both to guide the VLM in producing the output (perhaps) and to verify said output with regex, flagging it. 
- There are always 3 columns in a row
- The first column is a name: only alphabetical letters
- The second column can have hyphens, alphabets or numbers but it belongs from a finite set of possibilities which would benefit from having a dictionary VLM can refer to while deciding what it is
- The third column, phone numbers, is always exactly 10 digits 0-9
- There are always 31 rows in a page

#### Output format
- Columns: name, location, dictionary key, phone number, recheck (bool), checks_failed 
- dictionary key is defined below and refers to the location name
- recheck is there to flag any entry not passing the checks on the first go so that we can manually review it (true = review it, false = it's all chill)
- checks_failed is for when LLM could not parse anything; fill the value not extracted as NaN, i'll come and fill.
- Initialy everything is kept in separate files only, don't combine. we'll combined at the end (and even then with comments on page number)

#### Dictionary
- before everything, we do another series of splice - read - form a dictionary of all the value of column 2, so that we can guide the VLM to choose from one of those outputs or (None, name) which makes the dict flag false and gives the name as col 2 value. 

- Doable with chosen X values and again a strong center bias. there may be variation in x values due to manual error and different structure of left vs right pages, but absorb all that into very decent margins. just cut off the col 1 and 3, not restrict to col 2. 

- again, verification round for all pages showing the spliced sections. 

- allow me to manually crop in some places if I want to (the input to VLM may not be of the same size)

- Identify two common regexes: Ph-XY type X,Y is a numeral (may be X=1, Y= nothing, so not exactly two numerals always. there can be 3 too. NEED TO NOT mistake Ph1 as Ph11). The other Regex is Sec-XY . sometimes it may be written SecXY or PhXY without the hyphen, then we should put it in. Aside from that, there are city/village names. I can verufy and correct once, and then vlm can choose from them. 

- when you extract, also give counts for everything

#### recheck
- things that extract but give json false should be given another VLM pass and be marked recheck true. If it fails again, make it checks_failed. 

### NaN values
in rare cases, there are genuine scenarios of NaN (no number for example in database). Treat them as checks_failed

