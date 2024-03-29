from pyspark.sql import SparkSession

from pyspark.sql.functions import (regexp_replace, regexp_extract,
								   concat_ws,count,desc)

spark = SparkSession.builder. \
  master('yarn-client'). \
  appName('Web logs Analysis'). \
  getOrCreate()

spark.conf.set('spark.sql.shuffle.partitions','8')

raw_data= spark.read.csv("/user/srikarthik/weblogs", \
	sep=' ',ignoreLeadingWhiteSpace=False, \
	ignoreTrailingWhiteSpace=False)


'''
Parsing Stage1:

1. Remove double quotation from request-string,user-agent,referral

Note: This has been achieved by spark.read.csv. 
Since spark.read.csv has an in_built function namely quote which 
ignores quotation (\"). Also unnecessary spaces are removed by
in_built functions ignoreLeadingWhiteSpace and  
ignoreTrailingWhiteSpace

2. Remove [ ] from date-time field

'''

parsed_data1= raw_data.withColumn('time', \
	regexp_replace(concat_ws(' ','_c3','_c4'),'\[|\]',''))\
	.drop('_c3','_c4').toDF('Remote_IP','Remote_log_name',\
		'user','request_string','status_code','byte_string', \
		'user_agent','referral','time')


"""
Parsing Stage2:


Parse request-string into structured format
/cat-1/cat-2/page?param 

 cat-1 cat-2 cat-3 cat-4 page param

"""

parsed_data2 = parsed_data1.withColumn('category1', \
	regexp_extract('request_string','/(.*?)/',1)). \
	withColumn('category2',regexp_extract('request_string','/(.*?)/(.*?)/',2)). \
	withColumn('page', regexp_extract('request_string','/(.*?)/(.*?)/(.*.html)',3)). \
	withColumn('param', regexp_extract('request_string','html(.*)',1))


# Handle bad records, store bad records in a specific file

""" 
creating variables for null count and not null count, 
to find out any badrecords after parsing stage
"""
PnullCount,PnotNullCount=dict(),dict() 

# Defining function for calculating null and non-null records count

def null_notnull(dfname,nameNull,nameNotNull):
	for i in dfname.columns:
		nameNull[i]=dfname.select( \
			dfname[i]).filter(dfname[i].isNull()).count()
		nameNotNull[i]=dfname.select(  \
			dfname[i]).filter(dfname[i].isNotNull()).count()
	return ("null_count is {0} '\n\n', notNull_count is {1}".  \
		format(nameNull,nameNotNull))

# Displaying initial stage null and non-null records count

print (null_notnull(parsed_data2,PnullCount,PnotNullCount))

list_of_nullColumns = []

if not any (PnullCount.values()):
	goodrecords= parsed_data2
else:
	goodrecords= parsed_data2.na.drop(thresh=1)
	list_of_nullColumns.extend(PnullCount.keys())	
	RDD= goodrecords.rdd.map(list).\
	filter(lambda x: any([True if i==None else False for i in x]))
	RDD.map(lambda x: '|'.join(str(i) for i in x)). \
	saveAsTextFile('/user/srikarthik/weblogs_badrecords')

#Q1: Count the number of page visited by each individual user (User wise page-visit distribution)


page_views= goodrecords.groupBy('Remote_IP'). \
            agg(count('page').alias('pagecount')). \
            sort(desc('pagecount'))


page_views.show()

# Save the records as tab delimited text file


page_views.rdd.map(lambda x: '\t'.join(str(i) for i in x)). \
   saveAsTextFile('/user/srikarthik/webpageviews')



#Q2: Count of page views by category-1

category1_views= goodrecords.groupBy('category1').   \
                 agg(count('page').alias('pagecount')).  \
                 sort(desc('pagecount'))


category1_views.show()

# Save the records as tab delimited text file

category1_views.rdd.map(lambda x: '\t'.join(str(i) for i in x)). \
   coalesce(1).saveAsTextFile('/user/srikarthik/category1views')