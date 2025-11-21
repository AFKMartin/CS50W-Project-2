from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from .models import *
from decimal import Decimal, InvalidOperation

def index(request):
    active_listings = AuctionListing.objects.filter(is_active=True)
    watching = []
    unread_notifications = 0

    if request.user.is_authenticated:
        watching = request.user.watchlist_items.values_list('listing', flat=True)
        unread_notifications = Notification.objects.filter(user=request.user, read=False).count()

    return render(request, "auctions/index.html", {
        "listings": active_listings,
        "watching": AuctionListing.objects.filter(id__in=watching),
        "unread_notifications": unread_notifications
    })

def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "auctions/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "auctions/login.html")

def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))

def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "auctions/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "auctions/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "auctions/register.html")

@login_required
def close_listing(request, listing_id):
    listing = get_object_or_404(AuctionListing, pk=listing_id)

    if listing.owner != request.user:
        return HttpResponse("Unauthorized", status=401)
    
    # Find the highest Bid
    highest_bid = listing.bids.order_by("-amount").first()
    listing.winner = highest_bid.user if highest_bid else None # In case no one Bid

    # Set listing active to false
    listing.is_active = False
    listing.save()

    # Create notification
    if highest_bid is not None:
        Notification.objects.create(
            user=highest_bid.user,
            message=f"You won the auction for '{listing.title}' with a bid of {highest_bid.amount}!"
        )

    return redirect("listing_detail", listing_id=listing_id)

def closed_listings(request):
    closed_auctions = AuctionListing.objects.filter(is_active=False) # Why the hell did I typo this
    return render(request, "auctions/closed_listings.html", {
        "listings": closed_auctions
    })

@login_required
def delete_listing(request, listing_id):
    listing = get_object_or_404(AuctionListing, pk=listing_id)

    # Only owner can delete
    if listing.owner != request.user:
        return HttpResponse("Unauthorized", status=401)

    listing.delete()
    return redirect("index")

@login_required
def create_listing(request):
    if request.method == "POST":
        title = request.POST["title"]
        description = request.POST["description"]
        starting_bid = request.POST["starting_bid"]
        image_url = request.POST.get("image_url")
        category_id = request.POST.get("category")

        category = Category.objects.get(pk=category_id) if category_id else None

        auction = AuctionListing(
            title=title,
            description=description,
            starting_bid=starting_bid,
            image_url=image_url,
            category=category,
            owner=request.user
        )
        auction.save()

        return HttpResponseRedirect(reverse("index"))
    
    else:
        categories = Category.objects.all()
        return render(request, "auctions/create_listing.html", {
            "categories": categories
        })
    
@login_required
def categories(request):
    categories = Category.objects.all()
    return render(request, "auctions/categories.html", {
        "categories": categories
    })

@login_required
def category_listings(request, category_id):
    watching = []
    if request.user.is_authenticated:
        watching = AuctionListing.objects.filter(watchlisted_by__user=request.user)
        
    category = Category.objects.get(id=category_id)
    listings = AuctionListing.objects.filter(category=category, is_active=True)
    
    return render(request, "auctions/category_listings.html", {
        "category": category,
        "listings": listings,
        "watching": watching
    })

@login_required
def watchlist(request):
    watched_listings = AuctionListing.objects.filter(
        watchlisted_by__user=request.user
    )

    return render(request, "auctions/watchlist.html", {
        "listings": watched_listings
    })

def listing_detail(request, listing_id):
    listing = get_object_or_404(AuctionListing, pk=listing_id)
    comments = listing.comments.all().order_by("-timestamp")
    
    # Determine if the user is watching this listing
    is_watching = False
    if request.user.is_authenticated:
        is_watching = Watchlist.objects.filter(user=request.user, listing=listing).exists()
    
    # If user submits a comment
    if request.method == "POST":
        text_comment = request.POST.get("comment")
        if text_comment.strip() != "":
            Comment.objects.create(
                auction_listing=listing,
                user=request.user,
                text_comment=text_comment
            )
        return redirect("listing_detail", listing_id=listing_id)

    return render(request, "auctions/listing_detail.html", {
        "listing": listing,
        "is_watching": is_watching,
        "comments": comments
    })

@login_required
def toggle_watchlist(request, listing_id):
    listing = get_object_or_404(AuctionListing, id=listing_id)

    watch_entry, created = Watchlist.objects.get_or_create(
        user=request.user,
        listing=listing
    )

    if not created:
        watch_entry.delete()

    return HttpResponseRedirect(request.META.get("HTTP_REFERER", reverse("index")))

@login_required
def place_bid(request, listing_id):
    listing = get_object_or_404(AuctionListing, pk=listing_id)

    if request.method == "POST":
        bid_raw = request.POST.get("bid_amount")

        # If empty value
        if not bid_raw:
            return render(request, "auctions/listing_detail.html", {
                "listing": listing,
                "is_watching": Watchlist.objects.filter(user=request.user, listing=listing).exists(),
                "error_message": "Error, you need to enter a bid amount."
            })

        # Convert to decimal
        try:
            bid_amount = Decimal(bid_raw)
        except (InvalidOperation, ValueError):
            return render(request, "auctions/listing_detail.html", {
                "listing": listing,
                "is_watching": Watchlist.objects.filter(user=request.user, listing=listing).exists(),
                "error_message": "Invalid bid value."
            })

        # Determine the current price
        highest = listing.bids.aggregate(max_amount=Max('amount'))["max_amount"]
        current_price = listing.starting_bid if highest is None else highest

        # Validate bid
        if bid_amount <= current_price:
            return render(request, "auctions/listing_detail.html", {
                "listing": listing,
                "is_watching": Watchlist.objects.filter(user=request.user, listing=listing).exists(),
                "error_message": f"Your bid must be higher than the current price (${current_price})."
            })

        # Create the bid
        with transaction.atomic():
            Bid.objects.create(
                auction_listing=listing,
                user=request.user,
                amount=bid_amount
            )
            listing.starting_bid = bid_amount
            listing.save()

        return render(request, "auctions/listing_detail.html", {
            "listing": listing,
            "is_watching": Watchlist.objects.filter(user=request.user, listing=listing).exists(),
            "success_message": "Your bid was placed successfully!"
        })

    return redirect("listing_detail", listing_id=listing_id)

@login_required
def notifications(request):
    user_notifications = Notification.objects.filter(user=request.user).order_by("-created")
    return render(request, "auctions/notifications.html", {"notifications": user_notifications})  

@login_required
def mark_notification_read(request, notification_id):
    notif = get_object_or_404(Notification, id=notification_id, user=request.user)
    notif.read = True
    notif.save()
    return redirect("notifications")