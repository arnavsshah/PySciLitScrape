import scrape
import os
import openai

openai.api_key = os.environ['OPENAI_API_KEY']

def LLM(prompt, model='text-davinci-003'):
    if model == 'text-davinci-003':
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            max_tokens=500,
            temperature=0.6,
        )
        return response.choices[0].text
    else:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.6,
        )
        return response.choices[0].message.content


def generate_summary(author_information, model='text-davinci-003'):
    abstract_info = [f"Title: {d['title']}\nAbstract: {d['abstract'].replace('        △ Less', '')}" for d in author_information]
    approximate_tokens_per_abstract = [len(x)//4 for x in abstract_info]
    token_count = 0
    paper_group = []
    paper_group.append([])

    summary_length = 700
    bin_size_in_tokens = ((4097 if model == 'text-davinci-003' else 8000) - summary_length) * 0.8

    for tokens, paper in zip(approximate_tokens_per_abstract, abstract_info):
        if token_count + tokens > bin_size_in_tokens:
            paper_group.append([])
            token_count = 0

        paper_group[-1].append(paper)
        token_count += tokens

    summary_prompt_header = f"""Write a detailed summary of the abstracts listed below.
The summary should be around 3-4 paragraphs.
The audience reading the summary is a researcher in the field. 

Be plain, direct, unambiguous, and specific. 

Avoid platitudes and generalities.
For instance, for researchers, you should never say someone is a "distinguished researcher" who has "significant contributions" or similar. 
For their work don't say their work is "groundbreaking" nor "influential" or similar. 
That is be sober. 

Furthermore, be general and don't give an itemization paper by paper. Group the paper abstracts into broad efforts. 
Do not, for example give a summary with structure: "The first paper ... The second paper ... The third paper ..." etc. 

Abstract list:
"""

    summaries = []
    for group in paper_group:
        prompt = summary_prompt_header + '\n'.join(group)
        summaries.append(LLM(prompt, model=model))

    final_summary = combine_summaries(bin_size_in_tokens, summaries, model=model)
    return final_summary



def combine_summaries(bin_size_in_tokens, summaries, model='text-davinci-003'):
    summary_combiner = f"""Write a detailed summary by combining the summaries below.
The summary should be around 3-4 paragraphs.
The audience reading the summary is a researcher in the field. 

Be plain, direct, unambiguous, and specific. 

Avoid platitudes and generalities.
For instance, for researchers, you should never say someone is a "distinguished researcher" who has "significant contributions" or similar. 
For their work don't say their work is "groundbreaking" nor "influential" or similar. 
That is be sober. 

Summary list:
"""
    if len(summaries) == 1:
        return summaries[0]

    token_count = 0
    approximate_tokens_per_abstract = [len(s) / 4 for s in summaries]
    summary_group = []
    summary_group.append([])
    for tokens, summary in zip(approximate_tokens_per_abstract, summaries):
        if token_count + tokens > bin_size_in_tokens:
            summary_group.append([])
            token_count = 0

        summary_group[-1].append(summary)
        token_count += tokens
    new_summaries = []
    for group in summary_group:
        prompt = summary_combiner + '\n'.join(group)
        new_summaries.append(LLM(prompt, model))

    return combine_summaries(bin_size_in_tokens, new_summaries)



def generate_author_bio(author_information, summary, author_name, model):
    prompt = f"""Write a detailed biography, which is around 3-4 paragraphs, of a researcher whose research is summarized below.
    
    Be plain, direct, unambiguous, and specific. Avoid platitudes and generalities.
    
    For instance, for researchers, you should never say someone is a "distinguished researcher" who has "significant contributions" or similar. 
    For their work shouldn't be "groundbreaking" nor "influential"
    
    The researcher's name is {author_name}.
    
    A summary of their work:
    
    {summary} 
    """
    return LLM(prompt, model=model)

def Large_LLM(prompt, model='text-davinci-003', max_tokens=500):
    if model == 'text-davinci-003':
        response = openai.Completion.create(
            model="text-davinci-003",
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=0.6,
        )
        return response.choices[0].text
    else:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.6,
        )
        return response.choices[0].message.content


# print(Large_LLM(prompt, model='gpt4', max_tokens=3500))

# todo: remove all
author_name = 'Karthik Narasimhan'
url = 'https://arxiv.org/search/cs?query=Karthik+Narasimhan&searchtype=author&size=200'
information = scrape.get_all_papers_info(url, 200)
summary = generate_summary(information, model='gpt4')
#
# print('SUMMARY')
# print(summary)
# bio = generate_author_bio(information, summary, author_name=author_name, model='gpt4')
#
# print('BIO')
# print(bio)
#

