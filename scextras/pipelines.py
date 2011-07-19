
class SpiderFieldPipeline(object):
    def process_item(self, item, spider):
        item['spider'] = spider.name
        return item
