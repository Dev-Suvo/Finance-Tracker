from django.shortcuts import render, redirect
from django.contrib import messages



def index(request):

    if request.method == "POST":
        description = request.POST.get('description')
        amount = request.POST.get('amount')

        description = description.strip()
        
        if not description:
            messages.info(request, "Description cannot be blank!!")
            return redirect('/')
        
        if not amount:
            messages.info(request, "Amount is required!!")
            return redirect('/')
        

        try:
            amount = float(amount)
            print(amount,type(amount),description,type(description))

        except ValueError:
            messages.info(request, "Please enter a valid number!!")
            return redirect('/')
        
        

        return redirect('/')





    return render(request, 'index.html')