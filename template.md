Title: {{ title }}
Category: linklist
Link: {{ link }}
Date: {{ date }}
Tags: {{ tags }}
Status: draft

{% for cline in contents.split('\n') %}
> {{ cline }}
{% endfor %}