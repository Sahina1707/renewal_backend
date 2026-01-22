from django.contrib import admin
from .models import Survey, SurveyQuestion, SurveySubmission, QuestionAnswer

class QuestionInline(admin.TabularInline):
    model = SurveyQuestion
    extra = 0

class AnswerInline(admin.TabularInline):
    model = QuestionAnswer
    extra = 0
    readonly_fields = ('question', 'answer_value')

@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'created_at')
    inlines = [QuestionInline]

@admin.register(SurveySubmission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('id', 'survey', 'rating', 'status', 'created_at')
    list_filter = ('status', 'rating')
    inlines = [AnswerInline]