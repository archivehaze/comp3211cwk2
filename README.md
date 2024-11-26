# News Headline Serverless Workflow
This app automates the collection, processing, and presentation of news articles using Azure Functions and a SQL database. It performs the following tasks:

- Fetch News: Periodically retrieves top headlines using the News API and stores them in an Azure SQL database.
- Summarisation: Processes article descriptions to generate concise summaries using the Sumy library.
- Sentiment Analysis: Analyzes the sentiment of summaries (positive or negative) with NLTK.
- User-Friendly Display: Provides an HTTP endpoint to display today's headlines, summaries, and sentiment in a styled HTML format.

## Database table creation
Below is the SQL code required to create the database table
```sql
CREATE TABLE Articles (
    ArticleID INT IDENTITY PRIMARY KEY,
    Title NVARCHAR(MAX),
    Description NVARCHAR(MAX),
    URL NVARCHAR(MAX),
    PublishedDate DATETIME,
    Processed BIT DEFAULT 0,
    Summary NVARCHAR(MAX),
    Sentiment NVARCHAR(50)
);
```
Below is the SQL code required to enable change tracking on the database table. This is needed for the sql trigger functions.
```sql
ALTER DATABASE myFreeDB
SET CHANGE_TRACKING = ON;

ALTER TABLE [dbo].[Articles] 
ENABLE CHANGE_TRACKING;
```
